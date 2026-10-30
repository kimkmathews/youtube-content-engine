---
name: show-notes
description: Ready-to-paste YouTube description / podcast show notes with real clickable timestamps, key takeaways and resources mentioned. Use for show notes, a video description, or timestamps.
output_file: show_notes.md
strategy: reduce
rubric:
  - Starts with a 2-3 sentence description of the video.
  - Has a timestamp list in YouTube format (mm:ss Title, first entry 00:00), using only timestamps from the notes.
  - Lists the key takeaways.
  - Lists tools, links, people or resources mentioned, if any were mentioned.
  - Contains only the show notes -- no meta-commentary.
---

# Show Notes

Write show notes the creator could paste straight into the video's description.

## Output

1. A 2-3 sentence description of what the viewer will learn.
2. `Timestamps` -- one line per chapter in YouTube's clickable format: `00:00 Intro`, `03:15 Setting up the project`. The first line must be `00:00`. Use only timestamps that appear in the notes, and keep titles under 60 characters.
3. `Key takeaways` -- 3-6 bullets.
4. `Resources mentioned` -- tools, libraries, books, people or links named in the video. Omit this section if none were mentioned; never invent URLs.

Use plain text with minimal Markdown (YouTube descriptions don't render it): no headings beyond simple section labels.
