"""FastAPI entrypoint: chat API + static chat page."""

import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import agent, db

load_dotenv()

app = FastAPI(title="ai-agents — AI Secretary")

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

# Per-session message history (in-memory for the POC; transcripts are logged
# to SQLite for review).
_sessions: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str


@app.get("/")
def chat_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty.")

    session_id = req.session_id or uuid.uuid4().hex
    history = _sessions.get(session_id, [])

    _log(session_id, "user", req.message)
    try:
        reply, history = agent.run_turn(history, req.message)
    except Exception as exc:  # surface a friendly error, log the real one
        _log(session_id, "assistant", f"[error] {exc}")
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc

    _sessions[session_id] = history
    _log(session_id, "assistant", reply)
    return ChatResponse(session_id=session_id, reply=reply)


def _log(session_id: str, role: str, content: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO conversation_log (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()
