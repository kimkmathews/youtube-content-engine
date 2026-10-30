# YouTube Content Engine

Turns a YouTube video into ready-to-use content (blog post, lecture notes, chapters, show notes, LinkedIn post, X thread, quiz and flashcards, SEO pack) through a chat interface. It runs on open-weight models via OpenRouter.

## Setup

```bash
uv venv && uv pip install -r requirements.txt
cp .env.example .env   # then set OPENROUTER_API_KEY
```

## Run

```bash
.venv/Scripts/python run_ui.py     # Streamlit dashboard at http://localhost:8501
.venv/Scripts/python main.py       # terminal chat
```

Paste a YouTube URL and say what you want, for example "lecture notes and a LinkedIn post, technical, for experts". Outputs go to `workspace/<session>/<video_id>/`, and the dashboard sidebar has a download button for each file.

## How it works

```
Orchestrator agent (DeepAgents, GLM)            src/core/runtime.py
  tools: ingest_video, produce_content          src/core/tools.py
  subagent: reviser (fork mode) for edits
  middleware: last-used preferences in prompt, retry, call limit, model fallback
        │
        └─ produce_content → deterministic pipeline   src/pipeline/produce.py
             1. ingest   transcript + chapters → timestamped chunks (cached per video)
             2. map      one structured digest per chunk, in parallel (cached by content hash)
             3. write    reduce formats: 1 call over all digests
                         per_chunk formats: 1 call per chunk + 1 for intro/closing
             4. grade    rubric check per format; one rewrite + re-grade on failure
```

The orchestrator only makes the conversational decisions. Content production is plain code, so a 12-chapter video in four formats costs about 20–25 model calls instead of about 90. Each run logs its call count, tokens and cost.

## Adding a format

Create `skills/<name>/SKILL.md`:

```yaml
---
name: my-format              # must match the folder name
description: What it is and when to use it (shown to the orchestrator)
output_file: my_format.md
strategy: reduce             # or per_chunk for long, section-by-section documents
rubric:
  - Each criterion the grader checks
---
Writing instructions...
```

That's all. No Python changes are needed.

## Models

Each role is set by one env var in `.env` (see `.env.example`): `ORCHESTRATOR_MODEL`, `WRITER_MODEL`, `WORKER_MODEL`, `GRADER_MODEL`, `FALLBACK_MODEL`. Requests are routed only to OpenRouter hosts that support the parameters sent, and data collection is denied by default.

## Tests

```bash
.venv/Scripts/python -m unittest tests.test_extractors tests.test_workspace tests.test_pipeline tests.test_runtime_wiring
```

The tests use fake models, so they need no API key and no network.
