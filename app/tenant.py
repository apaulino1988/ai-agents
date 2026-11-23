"""Per-request tenant context.

The request layer (webhook / chat endpoint) resolves the tenant once and sets
this ContextVar; the agent and tool layers read it and pass an explicit
business_id into the service layer. This keeps agent entry points
signature-compatible with single-tenant callers (and their tests) while the
services stay explicit and hidden-state-free.
"""

from contextvars import ContextVar

current_business_id: ContextVar[int] = ContextVar("current_business_id", default=1)
