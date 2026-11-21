"""The Secretary agent: Claude with booking tools and the business profile."""

import datetime

import anthropic

from app.services import knowledge
from app.tools import TOOLS, execute_tool

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_TOOL_TURNS = 10

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def system_prompt() -> list[dict]:
    """Stable system prompt with the business profile, cached across requests."""
    text = f"""You are the friendly, professional AI Secretary for the business below. You handle the front office over web chat: answering questions about services, prices, and hours, giving quotes, and booking, rescheduling, or cancelling appointments.

{knowledge.profile_as_prompt_text()}

Rules:
- Answer only from the business profile above and your tools. Never invent services, prices, availability, or policies. If a price "may vary", say so.
- To book: confirm the service, check availability with the tool, offer concrete times, then collect the customer's name and phone number before booking. Confirm the booking with its appointment id.
- After every successful booking or reschedule, delegate a confirmation reminder to the Follow-up agent with the schedule_followup tool, then let the customer know they'll receive a reminder before their appointment. Never mention internal agents or tools.
- For reschedules/cancellations, look the customer up by phone number and confirm which appointment before changing anything. Mention the cancellation policy when relevant.
- Dates the customer gives like "tomorrow" or "next Thursday" must be resolved using the current date provided in the conversation.
- If a customer confirms attendance (e.g. replies CONFIRM to a reminder), find their upcoming appointment by their phone number and mark it confirmed with confirm_appointment, then acknowledge briefly.
- Reply in the customer's language — if they write in Spanish, respond in Spanish.
- If you can't help with something, say so briefly and offer the business phone number.
- Keep replies warm, concise, and focused — this is a chat or SMS window, not email. On SMS, keep replies especially short."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _date_context() -> str:
    today = datetime.date.today()
    return f"[Context: today is {today.strftime('%A')}, {today.isoformat()}]"


def run_turn(messages: list[dict], user_message: str) -> tuple[str, list[dict]]:
    """Run one conversation turn (including any tool calls).

    Returns (reply_text, updated_messages). `messages` is the prior history in
    Messages API format; the caller persists the returned list.
    """
    messages = list(messages)
    messages.append(
        {"role": "user", "content": f"{_date_context()}\n{user_message}"}
    )

    for _ in range(MAX_TOOL_TURNS):
        response = client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt(),
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            messages.pop()
            return (
                (
                    "I'm sorry, I can't help with that. "
                    "Is there anything else I can do for you?"
                ),
                messages,
            )

        if response.stop_reason != "tool_use":
            reply = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return reply, messages

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result, is_error = execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    return (
        (
            "Sorry, I ran into trouble completing that. Please call us at "
            f"{knowledge.get_profile()['phone']} and we'll sort it out."
        ),
        messages,
    )
