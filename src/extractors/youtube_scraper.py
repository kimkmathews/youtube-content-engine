import json
import re
import urllib.request
from functools import lru_cache
from types import SimpleNamespace

from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi
import yt_dlp
from src.core.schema import VideoMetadata

_CHAPTER_LINE_RE = re.compile(r"\W{0,10}(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\W+(.+?)\s*$")
_URL_RE = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')


@lru_cache(maxsize=32)
def _extract_info(video_id: str) -> dict:
    """yt-dlp metadata for one video -- cached so metadata, chapters and the
    caption fallback share a single request per video per process."""
    # socket_timeout: without it a stalled connection hung a tool call indefinitely.
    ydl_opts = {'quiet': True, 'skip_download': True, 'socket_timeout': 30}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)


class YouTubeScraper:
    def extract_video_id(self, url: str) -> str:
        match = _URL_RE.search(url)
        if not match:
            raise ValueError(f"Invalid YouTube URL: {url}")
        return match.group(6)

    def get_info(self, url: str) -> dict:
        try:
            return _extract_info(self.extract_video_id(url))
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to fetch video info: {e}") from e

    def get_metadata(self, url: str) -> VideoMetadata:
        info = self.get_info(url)
        return VideoMetadata(
            video_id=self.extract_video_id(url),
            title=info.get('title', 'Unknown Title'),
            channel_name=info.get('uploader', 'Unknown Channel'),
            description=info.get('description', '') or '',
            length_seconds=info.get('duration', 0) or 0,
        )

    def get_chapters(self, url: str) -> list[dict] | None:
        """Ordered chapter list: [{'start': float, 'end': float|None, 'title': str}, ...].

        Prefers YouTube's native chapters (yt-dlp's `chapters` field); falls back to
        parsing a timestamped outline out of the description, since many creators list
        one even without using YouTube's chapter feature (e.g. "00:10:17 Setup"). Returns
        None if neither is present, or the description doesn't have at least 2 recognizable
        timestamp+title lines.
        """
        try:
            info = self.get_info(url)
        except RuntimeError:
            return None
        return self.chapters_from_info(info)

    def chapters_from_info(self, info: dict) -> list[dict] | None:
        native = info.get('chapters')
        if native:
            return [
                {
                    'start': float(c['start_time']),
                    'end': float(c['end_time']) if c.get('end_time') is not None else None,
                    'title': (c.get('title') or '').strip(),
                }
                for c in native
                if (c.get('title') or '').strip()
            ] or None
        return self._parse_description_chapters(info.get('description', '') or '')

    def _parse_description_chapters(self, description: str) -> list[dict] | None:
        entries = []
        for line in description.splitlines():
            match = _CHAPTER_LINE_RE.match(line.strip())
            if not match:
                continue
            h, m, s, title = match.groups()
            seconds = (int(h) * 3600 if h else 0) + int(m) * 60 + int(s)
            title = title.strip(" -*#:").strip()
            if title:
                entries.append({'start': float(seconds), 'title': title})

        if len(entries) < 2:
            return None

        entries.sort(key=lambda e: e['start'])
        for i, entry in enumerate(entries):
            entry['end'] = entries[i + 1]['start'] if i + 1 < len(entries) else None
        return entries

    def get_transcript(self, url: str) -> tuple[list, str]:
        """Timestamped transcript entries (`.text`, `.start`, `.duration`) and their language name.

        Prefers English; otherwise the first available transcript (manual before
        auto-generated) -- e.g. a Hindi-only video. If youtube-transcript-api fails
        (it gets IP-blocked after many requests, common on cloud hosts), falls back to
        yt-dlp's caption tracks, which go through a different path.
        """
        video_id = self.extract_video_id(url)
        try:
            return self.get_transcript_entries(video_id)
        except RuntimeError as api_error:
            try:
                entries = self.caption_entries_from_info(self.get_info(url))
            except Exception:
                entries = []
            if not entries:
                raise api_error
            return entries, "English"

    def get_transcript_entries(self, video_id: str) -> tuple[list, str]:
        try:
            transcripts = YouTubeTranscriptApi().list(video_id)
            try:
                transcript = transcripts.find_transcript(["en"])
            except NoTranscriptFound:
                transcript = next(iter(transcripts))
            fetched = transcript.fetch()
            return list(fetched), getattr(fetched, "language", None) or transcript.language_code
        except Exception as e:
            raise RuntimeError(f"Failed to extract transcript: {e}") from e

    def caption_entries_from_info(self, info: dict) -> list:
        """English captions (manual first, then auto) via yt-dlp's json3 track."""
        for tracks in (info.get('subtitles') or {}, info.get('automatic_captions') or {}):
            for lang in ('en', 'en-US', 'en-GB', 'en-orig'):
                fmt = next((f for f in tracks.get(lang, []) if f.get('ext') == 'json3'), None)
                if not fmt:
                    continue
                with urllib.request.urlopen(fmt['url'], timeout=30) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                entries = []
                for ev in data.get('events', []):
                    text = "".join(seg.get('utf8', '') for seg in ev.get('segs') or []).strip()
                    if text:
                        entries.append(SimpleNamespace(text=text, start=ev.get('tStartMs', 0) / 1000,
                                                       duration=ev.get('dDurationMs', 0) / 1000))
                if entries:
                    return entries
        return []
