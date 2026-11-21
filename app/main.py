"""FastAPI entrypoint: chat API + static chat page."""

import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import agent, db, followup_agent
from app.services import channels
from app.services import outbox as outbox_service
from app.services import tasks as tasks_service

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


@app.post("/webhooks/sms")
async def sms_webhook(request: Request) -> Response:
    """Inbound SMS (Twilio): customer texts go to the Secretary; reply is TwiML."""
    form = dict(await request.form())
    if channels.validation_enabled():
        signature = request.headers.get("X-Twilio-Signature", "")
        if not channels.validate_signature(str(request.url), form, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature.")

    from_phone = (form.get("From") or "").strip()
    body = (form.get("Body") or "").strip()
    if not from_phone or not body:
        raise HTTPException(status_code=400, detail="Missing From or Body.")

    session_id = f"sms:{from_phone}"
    history = _sessions.get(session_id, [])
    _log(session_id, "user", body)
    reply, history = agent.run_turn(
        history, f"[Channel: SMS. Customer phone: {from_phone}]\n{body}"
    )
    _sessions[session_id] = history
    _log(session_id, "assistant", reply)

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(reply)}</Message></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.post("/agents/followup/run")
def run_followup(include_future: bool = False) -> dict:
    """Process due handoff tasks addressed to the Follow-up agent."""
    results = followup_agent.run_due_tasks(include_future=include_future)
    return {
        "processed": len(results),
        "results": [
            {"task_id": t["id"], "status": t["status"], "result": t["result"]}
            for t in results
        ],
    }


@app.get("/agents/tasks")
def agent_tasks() -> list[dict]:
    return tasks_service.list_tasks()


@app.get("/outbox")
def outbox_messages() -> list[dict]:
    return outbox_service.list_messages()


def _log(session_id: str, role: str, content: str) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO conversation_log (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()
