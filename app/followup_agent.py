"""The Follow-up agent: processes handoff tasks from other agents.

A separate Claude agent with its own role, prompt, and tools. Currently handles
`appointment_confirmation` tasks: compose a personalized reminder and send it
to the customer (outbox channel until M3 brings real SMS).
"""

import json

from app import agent as agent_client
from app.services import booking, channels, knowledge, tasks

MODEL = agent_client.MODEL
MAX_TOKENS = 4096
MAX_TOOL_TURNS = 5

AGENT_NAME = "followup"

TOOLS = [
    {
        "name": "get_appointment",
        "description": "Fetch full appointment details by id.",
        "input_schema": {
            "type": "object",
            "properties": {"appointment_id": {"type": "integer"}},
            "required": ["appointment_id"],
        },
    },
    {
        "name": "send_message",
        "description": (
            "Send a message to the customer's phone. Call exactly once per task "
            "with the final composed message."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to_phone": {"type": "string"},
                "body": {"type": "string", "description": "The message text, SMS-length"},
            },
            "required": ["to_phone", "body"],
        },
    },
]


def system_prompt() -> list[dict]:
    p = knowledge.get_profile()
    text = f"""You are the Follow-up agent on the office team of {p['name']}. Other agents delegate follow-up work to you; you complete it independently.

Business facts you may use:
{knowledge.profile_as_prompt_text()}

Rules:
- For an appointment confirmation task: fetch the appointment, then send ONE friendly SMS-length reminder to the customer. Include the service name, weekday + date, time, and location. Ask them to reply CONFIRM, or to call {p['phone']} to reschedule or cancel.
- Address the customer by first name. No internal jargon, no agent talk.
- Write in the customer's language if known from context (default English).
- After sending, reply with a one-line summary of what you did (this is logged as the task result)."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


def _execute_tool(name: str, tool_input: dict, task: dict) -> tuple[str, bool, bool]:
    """Returns (result, is_error, message_sent)."""
    try:
        if name == "get_appointment":
            return (
                json.dumps(booking.get_appointment(tool_input["appointment_id"])),
                False,
                False,
            )
        if name == "send_message":
            record = channels.send_preferred(
                to_phone=tool_input["to_phone"],
                body=tool_input["body"],
                appointment_id=task["payload"].get("appointment_id"),
            )
            return (
                json.dumps(
                    {"sent": True, "channel": record["channel"], "outbox_id": record["id"]}
                ),
                False,
                True,
            )
        return f"Unknown tool: {name}", True, False
    except (booking.BookingError, channels.ChannelError) as exc:
        return str(exc), True, False


def run_task(task: dict) -> dict:
    """Process one handoff task; marks it done or failed. Returns the task."""
    try:
        return _run_task_inner(task)
    except Exception as exc:  # noqa: BLE001 — mark failed, never block the queue
        return tasks.fail_task(task["id"], f"error: {exc}")


def _run_task_inner(task: dict) -> dict:
    if task["task_type"] != "appointment_confirmation":
        return tasks.fail_task(task["id"], f"Unknown task type {task['task_type']}")

    messages = [
        {
            "role": "user",
            "content": (
                f"Task #{task['id']} from the {task['from_agent']} agent: send an "
                "appointment confirmation reminder.\n"
                f"Payload: {json.dumps(task['payload'])}"
            ),
        }
    ]
    sent = False
    summary = ""

    for _ in range(MAX_TOOL_TURNS):
        response = agent_client.client().messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt(),
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            summary = "".join(
                b.text for b in response.content if b.type == "text"
            ).strip()
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result, is_error, did_send = _execute_tool(
                    block.name, block.input, task
                )
                sent = sent or did_send
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    if sent:
        return tasks.complete_task(task["id"], summary or "Reminder sent.")
    return tasks.fail_task(task["id"], summary or "No message was sent.")


def run_due_tasks(include_future: bool = False) -> list[dict]:
    """Process all due tasks addressed to this agent."""
    return [
        run_task(task)
        for task in tasks.due_tasks(AGENT_NAME, include_future=include_future)
    ]
