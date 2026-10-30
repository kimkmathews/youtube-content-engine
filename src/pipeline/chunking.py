"""Chapter-aware transcript chunking that keeps real timestamps.

Splits along the video's chapters when it has any (native or parsed from the
description), so each chunk carries its actual chapter title. Any chapter still too
big for one call -- or a chapterless video -- is split on caption-entry boundaries,
so every chunk keeps an exact start/end time. `[mm:ss]` markers are inserted into the
text so timestamped formats can cite real times instead of inventing them.
"""

import re

from config.settings import Config
from src.core.schema import Chunk


def fmt_ts(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _render(entries: list) -> str:
    parts, last_marker = [], None
    for e in entries:
        if last_marker is None or e.start - last_marker >= Config.TIMESTAMP_EVERY_SECONDS:
            parts.append(f"[{fmt_ts(e.start)}]")
            last_marker = e.start
        parts.append(e.text)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _split_by_size(entries: list, max_chars: int) -> list[list]:
    groups, current, size = [], [], 0
    for e in entries:
        if current and size + len(e.text) > max_chars:
            groups.append(current)
            current, size = [], 0
        current.append(e)
        size += len(e.text) + 1
    if current:
        groups.append(current)
    return groups


def build_chunks(entries: list, chapters: list[dict] | None, max_chars: int = Config.CHUNK_SIZE) -> list[Chunk]:
    sections: list[tuple[str | None, list]] = []
    if chapters:
        intro = [e for e in entries if e.start < chapters[0]["start"]]
        if intro:
            sections.append(("Intro", intro))
        for ch in chapters:
            end = ch["end"] if ch["end"] is not None else float("inf")
            in_chapter = [e for e in entries if ch["start"] <= e.start < end]
            if in_chapter:
                sections.append((ch["title"], in_chapter))
    else:
        sections.append((None, entries))

    chunks: list[Chunk] = []
    for title, section_entries in sections:
        groups = _split_by_size(section_entries, max_chars)
        for part, group in enumerate(groups, start=1):
            part_title = f"{title} (part {part}/{len(groups)})" if title and len(groups) > 1 else title
            last = group[-1]
            chunks.append(
                Chunk(
                    index=len(chunks) + 1,
                    title=part_title,
                    start=group[0].start,
                    end=last.start + getattr(last, "duration", 0),
                    text=_render(group),
                )
            )
    return chunks
