"""Agent middleware that sanitizes content on its way into the workspace.

Hooks `wrap_tool_call` (a DeepAgents/LangChain middleware primitive) around
the built-in `write_file` and `edit_file` filesystem tools, rewriting their
arguments through `FormatCleaner` before the real tool runs. This replaces
the original `FormatCleaner` class, which existed in the codebase but was
never wired into anything -- content was never actually cleaned.
"""

from typing import Any, Callable

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.middleware.format_cleaner import FormatCleaner

_CONTENT_ARG_BY_TOOL = {
    "write_file": "content",
    "edit_file": "new_string",
}


class ContentQualityMiddleware(AgentMiddleware):
    """Cleans markdown artifacts out of content before it's written to disk."""

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call["name"]
        content_arg = _CONTENT_ARG_BY_TOOL.get(tool_name)
        if content_arg is None:
            return handler(request)

        args = request.tool_call["args"]
        raw = args.get(content_arg)
        if not isinstance(raw, str) or not raw:
            return handler(request)

        cleaned = FormatCleaner.clean_markdown(raw)
        if cleaned == raw:
            return handler(request)

        modified_call = {**request.tool_call, "args": {**args, content_arg: cleaned}}
        return handler(request.override(tool_call=modified_call))
