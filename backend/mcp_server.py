from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.tools.crm_tool import CRMTool
from backend.tools.kb_tool import KnowledgeBaseTool
from backend.tools.order_tool import OrderTool
from backend.tools.ticket_tool import TicketTool


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    """Unified registry used by both the agent and the MCP endpoint."""

    def __init__(self, session: Session) -> None:
        self.order_tool = OrderTool(session)
        self.crm_tool = CRMTool(session)
        self.ticket_tool = TicketTool(session)
        self.kb_tool = KnowledgeBaseTool()
        self._tool_map = {
            "get_order_status": self.order_tool.get_order_status,
            "search_knowledge_base": self.kb_tool.search_knowledge_base,
            "create_support_ticket": self.ticket_tool.create_support_ticket,
            "get_customer_details": self.crm_tool.get_customer_details,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "get_order_status",
                "description": "Retrieve the status, tracking number, and ETA for an order.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                },
            },
            {
                "name": "search_knowledge_base",
                "description": "Search support documentation for policy and troubleshooting guidance.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "name": "create_support_ticket",
                "description": "Create a support ticket for issues that require a human follow-up.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "integer"},
                        "issue": {"type": "string"},
                    },
                    "required": ["customer_id", "issue"],
                },
            },
            {
                "name": "get_customer_details",
                "description": "Look up CRM details and recent orders for a customer.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"customer_id": {"type": "integer"}},
                    "required": ["customer_id"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tool_map.get(name)
        if tool is None:
            raise LookupError(f"Unknown tool: {name}")
        return tool(**arguments)


def create_mcp_router(session_factory: Any) -> APIRouter:
    router = APIRouter(prefix="/mcp", tags=["mcp"])

    @router.post("")
    def handle_mcp(request: MCPRequest) -> dict[str, Any]:
        with session_factory() as session:
            registry = ToolRegistry(session)
            try:
                if request.method == "initialize":
                    result = {
                        "protocolVersion": "2025-03-01",
                        "serverInfo": {"name": "ai-support-agent-mcp", "version": "1.0.0"},
                        "capabilities": {"tools": {"listChanged": False}},
                    }
                elif request.method == "tools/list":
                    result = {"tools": registry.list_tools()}
                elif request.method == "tools/call":
                    tool_name = request.params.get("name", "")
                    arguments = request.params.get("arguments", {})
                    payload = registry.call_tool(tool_name, arguments)
                    result = {
                        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
                        "structuredContent": payload,
                        "isError": False,
                    }
                else:
                    raise HTTPException(status_code=400, detail=f"Unsupported MCP method: {request.method}")

                return {"jsonrpc": "2.0", "id": request.id, "result": result}
            except (LookupError, ValueError) as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {"code": -32000, "message": str(exc)},
                }

    return router
