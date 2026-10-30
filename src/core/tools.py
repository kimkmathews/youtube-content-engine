"""Orchestrator tools. Content production is one deterministic tool call (see
src/pipeline/produce.py) instead of a per-chunk agent loop."""

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from src.core.schema import Audience, Context, Purpose, Tone, UserPreferences
from src.core.skill_files import load_skills
from src.pipeline import produce
from src.pipeline.chunking import fmt_ts

PREFS_NAMESPACE = "preferences"
PREFS_KEY = "last_used"


def load_preferences(store, user_id: str) -> UserPreferences | None:
    item = store.get((PREFS_NAMESPACE, user_id), PREFS_KEY) if store else None
    return UserPreferences.model_validate(item.value) if item else None


@tool
def ingest_video(url: str) -> str:
    """Fetch a YouTube video's metadata and transcript and report what it contains:
    title, channel, length, transcript language and its sections (chapters). Call this
    first for any new URL. Cached, so calling it again for the same video is free."""
    video = produce.ingest(url)
    meta = video.metadata
    lines = [
        f"Title: {meta.title}",
        f"Channel: {meta.channel_name}",
        f"Length: {fmt_ts(meta.length_seconds)}",
        f"Transcript language: {video.transcript_language}",
        f"Sections ({'from the video chapters' if video.chapters_detected else 'split by length'}):",
    ]
    lines += [f"  {fmt_ts(c.start)} {c.title or f'Part {c.index}'}" for c in video.chunks]
    return "\n".join(lines)


@tool
def produce_content(
    url: str,
    formats: list[str],
    tone: Tone,
    audience: Audience,
    purpose: Purpose,
    runtime: ToolRuntime[Context],
    language: str = "English",
    extra_instructions: str = "",
) -> str:
    """Generate one or more content formats for a YouTube video, all in one call.

    Runs the whole pipeline (transcript notes, writing, rubric quality check, one
    revision if needed) and writes each deliverable to the session workspace. Pass
    every format the user wants in a single call. `extra_instructions` carries any
    user requests beyond tone/audience/purpose (e.g. "focus on the deployment part").
    Returns each output path and its quality-check result.
    """
    prefs = UserPreferences(tone=tone, audience=audience, purpose=purpose, language=language)
    ctx = runtime.context
    if runtime.store is not None:
        runtime.store.put((PREFS_NAMESPACE, ctx.user_id), PREFS_KEY, prefs.model_dump())

    def progress(message: str) -> None:
        if runtime.stream_writer:
            runtime.stream_writer({"progress": message})

    results, usage = produce.produce(url, formats, prefs, ctx.session_id, extra_instructions, progress)
    lines = []
    for r in results:
        status = "passed quality check" if r.passed_rubric else "quality check flagged: " + "; ".join(r.failing_criteria)
        lines.append(f"- {r.skill_name}: {r.output_path} ({status})")
    lines.append(f"Usage: {usage}")
    return "\n".join(lines)


def _describe_formats() -> str:
    return "\n".join(f"- {s.name}: {s.description}" for s in load_skills().values())


produce_content.description += "\n\nAvailable formats:\n" + _describe_formats()
