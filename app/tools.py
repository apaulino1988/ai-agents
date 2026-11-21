"""Tool definitions and dispatch for the Secretary agent."""

import json

from app.services import booking

TOOLS = [
    {
        "name": "check_availability",
        "description": (
            "Check open appointment start times for a service on a given date. "
            "Call this before booking, and whenever the customer asks about "
            "availability. Returns a list of HH:MM start times; an empty list "
            "means the business is closed or fully booked that day."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "service_id": {
                    "type": "string",
                    "description": "Service id from the business profile (e.g. 'cleaning')",
                },
            },
            "required": ["date", "service_id"],
        },
    },
    {
        "name": "book_appointment",
        "description": (
            "Book an appointment. Only call after the customer has confirmed the "
            "service, date, time, and given their name and phone number. Returns "
            "the confirmed appointment with its id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM, 24-hour"},
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"},
            },
            "required": ["service_id", "date", "time", "customer_name", "customer_phone"],
        },
    },
    {
        "name": "find_appointments",
        "description": (
            "Find a customer's upcoming booked appointments by their phone number. "
            "Use this when a customer wants to check, reschedule, or cancel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"customer_phone": {"type": "string"}},
            "required": ["customer_phone"],
        },
    },
    {
        "name": "cancel_appointment",
        "description": (
            "Cancel a booked appointment by its id. Confirm with the customer "
            "before cancelling, and remind them of the cancellation policy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"appointment_id": {"type": "integer"}},
            "required": ["appointment_id"],
        },
    },
    {
        "name": "reschedule_appointment",
        "description": (
            "Move a booked appointment to a new date/time. Check availability for "
            "the new slot first. The old slot is freed automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer"},
                "new_date": {"type": "string", "description": "YYYY-MM-DD"},
                "new_time": {"type": "string", "description": "HH:MM, 24-hour"},
            },
            "required": ["appointment_id", "new_date", "new_time"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run a tool; returns (result_json, is_error)."""
    try:
        if name == "check_availability":
            result = booking.check_availability(
                tool_input["date"], tool_input["service_id"]
            )
        elif name == "book_appointment":
            result = booking.book_appointment(
                tool_input["service_id"],
                tool_input["date"],
                tool_input["time"],
                tool_input["customer_name"],
                tool_input["customer_phone"],
            )
        elif name == "find_appointments":
            result = booking.find_appointments(tool_input["customer_phone"])
        elif name == "cancel_appointment":
            result = booking.cancel_appointment(tool_input["appointment_id"])
        elif name == "reschedule_appointment":
            result = booking.reschedule_appointment(
                tool_input["appointment_id"],
                tool_input["new_date"],
                tool_input["new_time"],
            )
        else:
            return f"Unknown tool: {name}", True
        return json.dumps(result), False
    except booking.BookingError as exc:
        return str(exc), True
