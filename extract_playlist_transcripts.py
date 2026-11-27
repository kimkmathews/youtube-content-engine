"""Extract transcripts for every video in a YouTube playlist into separate Markdown files.

Reuses the project's YouTubeScraper (yt-dlp for metadata/chapters, youtube-transcript-api
for timestamped transcript entries). Transcripts are grouped under chapter headings when
the video has chapters (native or parsed from the description), otherwise into
fixed-length timestamped paragraphs.

Usage:
    python extract_playlist_transcripts.py
    python extract_playlist_transcripts.py --playlist <url> --out output/my_playlist --force
"""

import argparse
import re
import sys
import time
from pathlib import Path

import yt_dlp

from src.extractors.youtube_scraper import YouTubeScraper

DEFAULT_PLAYLIST = "https://www.youtube.com/playlist?list=PLviC8AFqAj5A9MHkRIn2fU5Ac2lEdJxNf"
DEFAULT_OUT = Path("output") / "claude_certified_architect"
PARAGRAPH_SECONDS = 60  # paragraph bucket size when a video has no chapters


def get_playlist_entries(playlist_url: str) -> tuple[str, list[dict]]:
    """Flat-extract the playlist (no per-video requests): returns (playlist title, entries)."""
    ydl_opts = {'quiet': True, 'skip_download': True, 'extract_flat': 'in_playlist'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
    entries = [e for e in (info.get('entries') or []) if e and e.get('id')]
    return info.get('title', 'Playlist'), entries


def slugify(text: str, max_len: int = 80) -> str:
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[\s_-]+', '-', text)[:max_len].strip('-') or 'untitled'


def fmt_ts(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def join_text(entries: list) -> str:
    return re.sub(r'\s+', ' ', " ".join(e.text for e in entries)).strip()


def build_body(entries: list, chapters: list[dict] | None) -> str:
    sections = []
    if chapters:
        for ch in chapters:
            end = ch['end'] if ch['end'] is not None else float('inf')
            text = join_text([e for e in entries if ch['start'] <= e.start < end])
            if text:
                sections.append(f"## [{fmt_ts(ch['start'])}] {ch['title']}\n\n{text}")
        # Anything spoken before the first chapter marker
        pre = join_text([e for e in entries if e.start < chapters[0]['start']])
        if pre:
            sections.insert(0, f"## [00:00] Intro\n\n{pre}")
    else:
        bucket, bucket_start = [], 0.0
        for e in entries:
            if bucket and e.start - bucket_start >= PARAGRAPH_SECONDS:
                sections.append(f"**[{fmt_ts(bucket_start)}]** {join_text(bucket)}")
                bucket = []
            if not bucket:
                bucket_start = e.start
            bucket.append(e)
        if bucket:
            sections.append(f"**[{fmt_ts(bucket_start)}]** {join_text(bucket)}")
    return "\n\n".join(sections)


def yaml_str(value: str) -> str:
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def build_markdown(index: int, playlist_title: str, playlist_url: str, info: dict,
                   video_id: str, body: str) -> str:
    title = info.get('title', 'Unknown Title')
    url = f"https://www.youtube.com/watch?v={video_id}"
    channel = info.get('uploader', 'Unknown Channel')
    duration = info.get('duration') or 0
    frontmatter = "\n".join([
        "---",
        f"title: {yaml_str(title)}",
        f"channel: {yaml_str(channel)}",
        f"playlist: {yaml_str(playlist_title)}",
        f"playlist_url: {playlist_url}",
        f"playlist_index: {index}",
        f"video_id: {video_id}",
        f"url: {url}",
        f"duration: {yaml_str(fmt_ts(duration))}",
        f"upload_date: {yaml_str(info.get('upload_date', ''))}",
        "---",
    ])
    return f"{frontmatter}\n\n# {title}\n\n**Channel:** {channel} · **Duration:** {fmt_ts(duration)} · [Watch on YouTube]({url})\n\n## Transcript\n\n{body}\n"


def process_video(scraper: YouTubeScraper, index: int, video_id: str, playlist_title: str,
                  playlist_url: str, out_dir: Path, force: bool) -> str:
    existing = list(out_dir.glob(f"{index:02d}-*.md"))
    if existing and not force:
        return f"skip (exists: {existing[0].name})"

    url = f"https://www.youtube.com/watch?v={video_id}"
    info = scraper.get_info(url)
    entries, _language = scraper.get_transcript(url)  # falls back to yt-dlp captions if the API is blocked
    body = build_body(entries, scraper.chapters_from_info(info))

    path = out_dir / f"{index:02d}-{slugify(info.get('title', video_id))}.md"
    for old in existing:
        if old != path:
            old.unlink()
    path.write_text(build_markdown(index, playlist_title, playlist_url, info, video_id, body),
                    encoding='utf-8')
    return f"saved {path.name}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--playlist', default=DEFAULT_PLAYLIST, help='YouTube playlist URL')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT, help='Output directory')
    parser.add_argument('--force', action='store_true', help='Re-download files that already exist')
    parser.add_argument('--delay', type=float, default=2.0, help='Seconds to wait between videos')
    parser.add_argument('--retries', type=int, default=3, help='Attempts per video')
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    scraper = YouTubeScraper()

    playlist_title, entries = get_playlist_entries(args.playlist)
    print(f"Playlist: {playlist_title} ({len(entries)} videos) -> {args.out}")

    failures = []
    for index, entry in enumerate(entries, start=1):
        video_id = entry['id']
        label = f"[{index:02d}/{len(entries)}] {entry.get('title') or video_id}"
        for attempt in range(1, args.retries + 1):
            try:
                print(f"{label}: {process_video(scraper, index, video_id, playlist_title, args.playlist, args.out, args.force)}")
                break
            except Exception as e:
                if attempt == args.retries:
                    print(f"{label}: FAILED - {e}")
                    failures.append((index, video_id, str(e)))
                else:
                    time.sleep(args.delay * attempt * 2)
        time.sleep(args.delay)

    print(f"\nDone: {len(entries) - len(failures)}/{len(entries)} succeeded.")
    for index, video_id, err in failures:
        print(f"  #{index:02d} {video_id}: {err[:200]}")
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
