"""FastAPI entrypoint: chat API, Twilio webhook, admin API + static chat page.

Multi-tenant: each request resolves its business once — web chat by slug,
webhooks by the receiving phone number — and sets the tenant ContextVar that
the agent/tool layer reads.
"""

import hmac
import logging
import os
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import agent, db, followup_agent
from app.services import channels, tenants
from app.services import outbox as outbox_service
from app.services import tasks as tasks_service
from app.tenant import current_business_id

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="ai-agents — AI Secretary")

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

# Per-session message history (in-memory for the POC; transcripts are logged
# to SQLite for review).
_sessions: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    business: str | None = None  # tenant slug; missing/unknown → default


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class BusinessCreate(BaseModel):
    slug: str
    name: str
    profile: dict
    timezone: str = "UTC"
    twilio_number: str | None = None
    whatsapp_sender: str | None = None
    calendar_id: str | None = None


class BusinessUpdate(BaseModel):
    name: str | None = None
    profile: dict | None = None
    timezone: str | None = None
    twilio_number: str | None = None
    whatsapp_sender: str | None = None
    calendar_id: str | None = None
    status: str | None = None


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

    business_id = _resolve_chat_business(req.business)
    current_business_id.set(business_id)

    session_id = req.session_id or uuid.uuid4().hex
    history = _sessions.get(session_id, [])

    _log(session_id, "user", req.message, business_id)
    try:
        reply, history = agent.run_turn(history, req.message)
    except Exception as exc:  # surface a friendly error, log the real one
        _log(session_id, "assistant", f"[error] {exc}", business_id)
        raise HTTPException(status_code=502, detail=f"Agent error: {exc}") from exc

    _sessions[session_id] = history
    _log(session_id, "assistant", reply, business_id)
    return ChatResponse(session_id=session_id, reply=reply)


def _resolve_chat_business(slug: str | None) -> int:
    """Spec AC-005: missing or unknown slug falls back to the default tenant."""
    if slug:
        business = tenants.get_by_slug(slug)
        if business:
            return business["id"]
    return tenants.DEFAULT_BUSINESS_ID


def _twiml(text: str) -> Response:
    return Response(
        content=(
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{escape(text)}</Message></Response>"
        ),
        media_type="application/xml",
    )


@app.post("/webhooks/sms")
async def sms_webhook(request: Request) -> Response:
    """Inbound SMS/WhatsApp (Twilio): customer messages go to the Secretary; reply is TwiML."""
    form = dict(await request.form())
    if channels.validation_enabled():
        signature = request.headers.get("X-Twilio-Signature", "")
        if not channels.validate_signature(str(request.url), form, signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature.")

    from_raw = (form.get("From") or "").strip()
    body = (form.get("Body") or "").strip()
    if not from_raw or not body:
        raise HTTPException(status_code=400, detail="Missing From or Body.")

    # Tenant routing by the receiving number (spec AC-004). A webhook without
    # `To` (pre-multi-tenant callers, tests) belongs to the default tenant.
    to_raw = (form.get("To") or "").strip()
    if to_raw:
        business = tenants.get_by_number(to_raw)
        if not business:
            logger.warning("Inbound message for unknown number %s dropped.", to_raw)
            return _twiml(
                "This number is not in service. Please check the number and try again."
            )
        if business["status"] != "active":
            logger.warning(
                "Inbound message for suspended business %s declined.", business["slug"]
            )
            return _twiml(
                "This business is currently unavailable. Please try again later."
            )
        business_id = business["id"]
    else:
        business_id = tenants.DEFAULT_BUSINESS_ID
    current_business_id.set(business_id)

    channel = "whatsapp" if from_raw.startswith("whatsapp:") else "sms"
    from_phone = channels.normalize_phone(from_raw)
    channels.record_preference(from_phone, channel, business_id=business_id)
    label = "WhatsApp" if channel == "whatsapp" else "SMS"

    session_id = f"b{business_id}:{channel}:{from_phone}"
    history = _sessions.get(session_id, [])
    _log(session_id, "user", body, business_id)
    reply, history = agent.run_turn(
        history, f"[Channel: {label}. Customer phone: {from_phone}]\n{body}"
    )
    _sessions[session_id] = history
    _log(session_id, "assistant", reply, business_id)

    return _twiml(reply)


def _require_admin(request: Request) -> None:
    """Admin API gate: hidden entirely without ADMIN_TOKEN (spec AC-008)."""
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        raise HTTPException(status_code=404, detail="Not found.")
    provided = request.headers.get("Authorization", "")
    if not hmac.compare_digest(provided, f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


@app.post("/admin/businesses", status_code=201)
def admin_create_business(req: BusinessCreate, request: Request) -> dict:
    _require_admin(request)
    try:
        return tenants.create_business(**req.model_dump())
    except tenants.TenantError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/admin/businesses/{slug}")
def admin_update_business(slug: str, req: BusinessUpdate, request: Request) -> dict:
    _require_admin(request)
    if not tenants.get_by_slug(slug):
        raise HTTPException(status_code=404, detail=f"No business '{slug}'.")
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        return tenants.update_business(slug, **fields)
    except tenants.TenantError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/admin/businesses")
def admin_list_businesses(request: Request) -> list[dict]:
    _require_admin(request)
    return tenants.list_businesses()


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


def _log(session_id: str, role: str, content: str, business_id: int = 1) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO conversation_log (business_id, session_id, role, content)"
            " VALUES (?, ?, ?, ?)",
            (business_id, session_id, role, content),
        )
        conn.commit()
