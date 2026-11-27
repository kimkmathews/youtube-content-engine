"""Path handling for tools that do their own file I/O.

DeepAgents' FilesystemPermission rules only guard its built-in fs tools. Any custom
tool that turns an agent-supplied path into a real one must go through `safe_path`,
or a prompt-injected transcript could steer it at `/.env` or the source tree.
"""

import os

from config.settings import Config


def virtual_path(session_id: str, *parts: str) -> str:
    """Agent-facing path for a file in a session workspace."""
    return "/" + "/".join(["workspace", session_id, *parts])


def safe_path(virtual: str, session_id: str) -> str:
    """Resolve a virtual `/workspace/<session_id>/...` path, refusing anything outside it."""
    root = os.path.realpath(Config.session_workspace_dir(session_id))
    real = os.path.realpath(os.path.join(Config.PROJECT_ROOT, virtual.lstrip("/\\")))
    if os.path.commonpath([real, root]) != root:
        raise ValueError(f"Path is outside this session's workspace: {virtual}")
    return real


def write_text(real_path: str, text: str) -> None:
    os.makedirs(os.path.dirname(real_path), exist_ok=True)
    with open(real_path, "w", encoding="utf-8") as f:
        f.write(text)
