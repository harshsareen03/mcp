from __future__ import annotations

from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.agent import SupportAgent
from backend.database.models import SessionLocal, get_session, init_db, seed_example_data
from backend.mcp_server import create_mcp_router


load_dotenv()

app = FastAPI(
    title="AI Customer Support Agent",
    description="FastAPI backend with MCP-style tools for support automation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(create_mcp_router(SessionLocal))


class ChatRequest(BaseModel):
    customer_id: int | None = Field(default=None, description="Optional authenticated customer ID")
    message: str = Field(..., min_length=1)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    used_tools: list[dict[str, Any]]
    escalated: bool
    conversation_summary: str
    llm_mode: bool


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_example_data()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def chat_ui() -> str:
    html_path = Path(__file__).resolve().parents[1] / "frontend" / "simple_chat_ui.html"
    return html_path.read_text(encoding="utf-8")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, session: Session = Depends(get_session)) -> ChatResponse:
    try:
        agent = SupportAgent(session)
        result = await agent.chat(
            message=request.message,
            customer_id=request.customer_id,
            conversation_history=request.conversation_history,
        )
        return ChatResponse(**result)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc
