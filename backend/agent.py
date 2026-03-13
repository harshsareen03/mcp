from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from backend.mcp_server import ToolRegistry


SYSTEM_PROMPT = """
You are an AI customer support agent.
Your job is to answer customer questions, use tools when needed, and escalate to a human agent when the issue cannot be resolved safely or confidently.

Rules:
- Use search_knowledge_base for policy and FAQ questions.
- Use get_order_status when an order ID is mentioned or order tracking is requested.
- Use get_customer_details when customer context would help.
- Use create_support_ticket when the issue needs human follow-up, the customer requests escalation, or you cannot fully resolve the issue.
- Keep answers concise, practical, and empathetic.
- Never invent order details, ticket IDs, or customer data.
""".strip()


class SupportAgent:
    """Orchestrates LLM calls and MCP tool execution."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.registry = ToolRegistry(session)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.client = None
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL"),
            )

    @property
    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_order_status",
                    "description": "Retrieve the status, tracking number, and ETA for an order.",
                    "parameters": {
                        "type": "object",
                        "properties": {"order_id": {"type": "string"}},
                        "required": ["order_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge_base",
                    "description": "Search support policies and troubleshooting content.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_support_ticket",
                    "description": "Create a ticket for human review or unresolved issues.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {"type": "integer"},
                            "issue": {"type": "string"},
                        },
                        "required": ["customer_id", "issue"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_customer_details",
                    "description": "Retrieve CRM profile details and recent orders.",
                    "parameters": {
                        "type": "object",
                        "properties": {"customer_id": {"type": "integer"}},
                        "required": ["customer_id"],
                    },
                },
            },
        ]

    async def chat(
        self,
        message: str,
        customer_id: int | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        conversation_history = conversation_history or []
        if self.client is None:
            return await self._chat_without_llm(message, customer_id, conversation_history)
        return await self._chat_with_llm(message, customer_id, conversation_history)

    async def _chat_with_llm(
        self,
        message: str,
        customer_id: int | None,
        conversation_history: list[dict[str, str]],
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(conversation_history)
        if customer_id is not None:
            messages.append(
                {
                    "role": "system",
                    "content": f"Authenticated customer_id for this session: {customer_id}",
                }
            )
        messages.append({"role": "user", "content": message})

        used_tools: list[dict[str, Any]] = []
        final_text = ""

        for _ in range(5):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_schemas,
                tool_choice="auto",
                temperature=0.2,
            )
            assistant_message = response.choices[0].message

            if assistant_message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in assistant_message.tool_calls
                        ],
                    }
                )

                for tool_call in assistant_message.tool_calls:
                    arguments = json.loads(tool_call.function.arguments)
                    result = self.registry.call_tool(tool_call.function.name, arguments)
                    used_tools.append({"name": tool_call.function.name, "arguments": arguments, "result": result})
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result),
                        }
                    )
                continue

            final_text = assistant_message.content or "I could not generate a response."
            break

        escalated = self._should_escalate(message, final_text, used_tools)
        summary = await self._generate_summary(message, final_text, used_tools, customer_id)

        return {
            "response": final_text,
            "used_tools": used_tools,
            "escalated": escalated,
            "conversation_summary": summary,
            "llm_mode": True,
        }

    async def _chat_without_llm(
        self,
        message: str,
        customer_id: int | None,
        conversation_history: list[dict[str, str]],
    ) -> dict[str, Any]:
        used_tools: list[dict[str, Any]] = []
        message_lower = message.lower()

        order_match = re.search(r"#?(\d{4,})", message)
        if order_match and any(keyword in message_lower for keyword in ["order", "track", "where", "delivery", "shipping"]):
            result = self.registry.call_tool("get_order_status", {"order_id": order_match.group(1)})
            used_tools.append({"name": "get_order_status", "arguments": {"order_id": order_match.group(1)}, "result": result})
            answer = (
                f"Order #{result['order_id']} for {result['item_name']} is currently {result['status']}. "
                f"Carrier: {result['shipping_carrier']}. Tracking: {result['tracking_number']}. "
                f"Estimated delivery: {result['estimated_delivery']}."
            )
            return {
                "response": answer,
                "used_tools": used_tools,
                "escalated": False,
                "conversation_summary": self._simple_summary(message, answer, used_tools, customer_id, conversation_history),
                "llm_mode": False,
            }

        kb_result = self.registry.call_tool("search_knowledge_base", {"query": message})
        used_tools.append({"name": "search_knowledge_base", "arguments": {"query": message}, "result": kb_result})

        if kb_result["results"]:
            article = kb_result["results"][0]
            answer = f"{article['title']}: {article['content']}"
            escalated = self._should_escalate(message, answer, used_tools)
        else:
            escalated = True
            if customer_id is not None:
                ticket = self.registry.call_tool(
                    "create_support_ticket",
                    {"customer_id": customer_id, "issue": message},
                )
                used_tools.append(
                    {
                        "name": "create_support_ticket",
                        "arguments": {"customer_id": customer_id, "issue": message},
                        "result": ticket,
                    }
                )
                answer = (
                    "I could not fully resolve that automatically, so I created a support ticket "
                    f"#{ticket['ticket_id']} for a human agent to review."
                )
            else:
                answer = "I could not fully resolve that automatically. Please provide a customer ID so I can create a support ticket."

        return {
            "response": answer,
            "used_tools": used_tools,
            "escalated": escalated,
            "conversation_summary": self._simple_summary(message, answer, used_tools, customer_id, conversation_history),
            "llm_mode": False,
        }

    def _should_escalate(self, user_message: str, agent_response: str, used_tools: list[dict[str, Any]]) -> bool:
        combined_text = f"{user_message} {agent_response}".lower()
        escalation_signals = ["human", "agent", "refund", "cancel", "lawsuit", "complaint", "angry", "damaged", "not solved"]
        if any(signal in combined_text for signal in escalation_signals):
            return True
        return any(tool["name"] == "create_support_ticket" for tool in used_tools)

    async def _generate_summary(
        self,
        user_message: str,
        final_text: str,
        used_tools: list[dict[str, Any]],
        customer_id: int | None,
    ) -> str:
        if self.client is None:
            return self._simple_summary(user_message, final_text, used_tools, customer_id, [])

        summary_prompt = (
            "Summarize this support interaction in 3 short sentences for a human support agent. "
            "Include customer intent, actions taken, and any open follow-up."
        )
        summary_response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": summary_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "customer_id": customer_id,
                            "user_message": user_message,
                            "assistant_response": final_text,
                            "used_tools": used_tools,
                        }
                    ),
                },
            ],
        )
        return summary_response.choices[0].message.content or "Summary unavailable."

    def _simple_summary(
        self,
        user_message: str,
        final_text: str,
        used_tools: list[dict[str, Any]],
        customer_id: int | None,
        conversation_history: list[dict[str, str]],
    ) -> str:
        tool_names = ", ".join(tool["name"] for tool in used_tools) or "no tools"
        history_count = len(conversation_history)
        return (
            f"Customer {customer_id or 'unknown'} asked: {user_message}. "
            f"Agent responded: {final_text}. "
            f"Tools used: {tool_names}. Prior turns: {history_count}."
        )
