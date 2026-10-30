"""Appends the user's last-used preferences to the orchestrator's system prompt.

Replaces the old "read_file /preferences/last_used.json" step the agent had to take
every session: one tool round-trip saved, and the agent can't forget to do it.
Appended at the end so the cached static prompt prefix stays unchanged.
"""

from typing import Any, Callable

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from src.core.tools import load_preferences


class PreferencesPromptMiddleware(AgentMiddleware):
    def wrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> Any:
        prefs = load_preferences(request.runtime.store, request.runtime.context.user_id)
        if prefs is None:
            note = "## User preferences\nNone saved yet (first session): ask for tone, audience and purpose."
        else:
            note = (
                "## User preferences\nLast used: "
                f"tone={prefs.tone}, audience={prefs.audience}, purpose={prefs.purpose}, language={prefs.language}. "
                "Offer to reuse them instead of asking from scratch."
            )
        current = request.system_message.content if request.system_message else ""
        if isinstance(current, list):
            content = [*current, {"type": "text", "text": note}]
        else:
            content = f"{current}\n\n{note}" if current else note
        return handler(request.override(system_message=SystemMessage(content=content)))
