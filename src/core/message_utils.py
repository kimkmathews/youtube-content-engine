"""Shared helper for extracting plain text from a chat model response.

Different models return `AIMessage.content` differently: some as a plain
string, others (observed live with gemini-3.5-flash-lite) as a list of
content blocks (`[{"type": "text", "text": "...", "extras": {...}}, ...]`).
Anything that does `response.content.replace(...)` or similar needs to go
through this first.
"""


def extract_text(content) -> str:
    if isinstance(content, list):
        text_blocks = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(text_blocks) if text_blocks else str(content)
    return content
