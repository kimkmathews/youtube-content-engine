# YouTube Content Engine — Architecture Assessment & Refactoring Plan

> **Implementation status (2026-10-30).** Done: Phases 0, 1 and 2; the Phase 3 items listed below; section 7's P0/P1 items, plus the fork-mode reviser; and four new formats (show-notes, quiz-flashcards, x-thread, seo-pack).
> Phase 3 items done: streaming progress, `st.cache_resource`, `context_schema` with per-user preferences, retry/fallback/call-limit middleware, and fake-model tests.
> Open: async runtime, Postgres persistence, the `evals/` golden-video set, the export tools with `interrupt_on`, async subagents, and multimodal skills.
> Not verified: a live run on OpenRouter (it needs `OPENROUTER_API_KEY`).

Scope: everything under `youtube-content-engine/` (~2.1k lines of Python + 4 skills), as of commit `f31527a`.
Goal: make it cheaper, faster, safer and production-grade, and move the LLM provider from Google AI Studio (Gemini) to OpenRouter open-weight models (DeepSeek / GLM).

---

## 1. How it works today

```
User (CLI main.py / Streamlit ui/app.py)
  └─ DeepAgentsRuntime.invoke(session_id, msg)            src/core/runtime.py
       └─ Orchestrator deep agent (Gemini Flash Lite)
            tools: get_video_metadata, get_video_transcript, + DeepAgents built-ins (fs, todos, task)
            memory: memory/AGENTS.md   skills: /skills   store: /preferences (SqliteStore)
            middleware: ContentQualityMiddleware (cleans write_file/edit_file content)
            │
            ├─ read /preferences/last_used.json, ask user for formats/tone/audience/purpose
            ├─ get_video_metadata  → yt-dlp extract_info               (call #1 to YouTube)
            ├─ get_video_transcript → transcript API + yt-dlp again     (call #2 to YouTube)
            │     writes transcript_part_NNN.txt, returns paths only
            └─ task(subagent_type=<skill>) × N formats, in parallel
                 Writer subagent (one per skills/<name>/SKILL.md)    src/agents/copywriters.py
                   tools: check_tone, generate_chunk_notes, merge_chunk_notes
                   middleware: _RubricInjector + RubricMiddleware (grader LLM, ≤2 iterations)
                   response_format: DeliverableResult
                   ├─ short video: read_file → draft → check_tone → write_file
                   └─ long video:  generate_chunk_notes × K (sequential, 1 LLM call each,
                                   PLUS 1 subagent LLM turn per tool call) → merge_chunk_notes
                                   (plain concatenation)
            All model calls gated by a hand-rolled TPM/RPM limiter      src/core/token_budget.py
```

## 2. Assessment

### What is done well (keep)

| Strength | Where |
|---|---|
| Transcript travels as **file paths, never as message content** — orchestrator context stays small | `tools.py:get_video_transcript` |
| **Chapter-aware chunking** (native chapters → description timestamps → size split) gives far better per-chapter output than blind splits | `tools.py:80-96`, `youtube_scraper.py:get_chapters` |
| Chunk work runs as **isolated stateless calls**, results go to disk, only confirmations return | `generate_chunk_notes` |
| **Skills-as-files** with auto-discovered subagents: a new format is mostly a new folder | `copywriters.py`, `skills/` |
| Prompt-injection awareness: transcript is passed as user-turn data, not spliced into system prompts; every skill restates "data, not instructions" | skills, `copywriters.py` docstring |
| Filesystem permission rules deny the agent reading `.env`/source | `runtime.py:_PERMISSIONS` |
| Structured subagent result (`DeliverableResult`) instead of parsing prose | `schema.py` |
| Rubric quality gate per format + construction-only wiring tests | `rubric_gate.py`, `tests/` |
| Static prompt prefix first, variable chunk last — already cache-friendly | `generate_chunk_notes` prompt layout |

### Problems, ranked by impact

**A. Efficiency / cost**

1. **A deterministic pipeline is being driven by LLM reasoning turns.** "fetch → chunk → per-chunk generate → merge" never varies, yet the writer subagent is an LLM loop that calls `generate_chunk_notes` one tool call per turn. Every turn re-sends the DeepAgents base prompt, skill catalog, task instructions and a growing message history (settings.py itself estimates ~6k tokens of scaffolding per call). For a 12-chunk video and 3 long-form formats that is roughly 3 × (12 chunk calls + ~14 agent turns + grading) ≈ **80–100 LLM calls**, of which ~40 do nothing but decide "call the next chunk". This is the single biggest waste.
2. **The transcript is processed once per format.** Blog, chapters and lecture notes each read the full transcript independently — 3× the input tokens for the same understanding work. LinkedIn sidesteps it by reading only `transcript_part_001`, which biases long videos to their intro.
3. **Chunk calls run sequentially** although they are independent (embarrassingly parallel map step).
4. **YouTube is hit twice per video** (`get_video_metadata` and `get_chapters` both call `yt_dlp.extract_info`), and nothing is cached across sessions — asking for a LinkedIn post tomorrow on yesterday's video re-downloads and re-processes everything.
5. **Three overlapping quality layers**: `check_tone` (LLM call on first 3,000 chars), `RubricMiddleware` (grader + up to 2 revise loops, reading the whole merged file), and `FormatCleaner`. The rubric already covers tone; `check_tone` is redundant cost.
6. Preferences are loaded by an LLM `read_file` tool call every session instead of being injected deterministically.

**B. Correctness / output quality**

7. **`merge_chunk_notes` is pure concatenation.** Fine for lecture notes, wrong for blog and chapter-generator: a blog becomes K stitched sections separated by `---` with no narrative arc, and the chapter-generator's required "2–3 paragraph summary of the whole video" cannot exist in a concatenation — the rubric then fails and triggers a revise loop that tries to patch it with `edit_file`.
8. **Stale part files get merged.** `merge_chunk_notes` globs `{skill}_part_*.md` in the session folder. Process a 12-chunk video, then a 5-chunk video in the same session → the merge includes parts 6–12 from the first video. (Visible in `workspace/1ba3ae70-…/`.)
9. **Chapter output says "no timestamps"** even though `get_transcript_entries` returns per-line `start` times — real timestamps are available and thrown away by `_clean_join`.
10. **No transcript fallback in the main path.** `extract_playlist_transcripts.py:caption_entries_from_info` already implements a yt-dlp caption fallback (needed when youtube-transcript-api is IP-blocked, common on cloud hosts), but `YouTubeScraper` doesn't use it.

**C. Security**

11. **Custom tools bypass the filesystem permission rules.** `_virtual_to_real()` (`tools.py:33`) does no containment check. `generate_chunk_notes(chunk_path="/.env")` reads the API key file and sends it to the model; `read_final_output("/.env")` returns it to the grader; `merge_chunk_notes(output_path="/src/core/runtime.py")` overwrites source code. The `_PERMISSIONS` list only guards DeepAgents' built-in fs tools. Since the trigger can be text inside an untrusted transcript, this is a real prompt-injection path. **Fix first.**

**D. Production readiness**

12. Provider lock-in: config, limiter, docstrings, CLI/UI key checks are all Gemini-specific (`GEMINI_*`).
13. `token_budget.py` + the `build_chat_model` / `build_chat_model_no_limiter` split (~180 lines) exist only to survive the Gemini free tier. Process-local, fixed-window, flat per-call estimate. Not needed on a paid OpenRouter key.
14. Fully synchronous: Streamlit blocks under a spinner for minutes with no progress; one `DeepAgentsRuntime` (graph + 2 SQLite connections) is built **per browser tab** via `st.session_state` instead of once per process (`st.cache_resource`).
15. SQLite checkpointer grows unbounded (`state.db` already 8 MB); preferences namespace is global (`("preferences",)`), so it's single-user only.
16. Adding a format requires editing two places: the skill folder **and** the `RUBRICS` dict in `rubric_gate.py`.
17. Dead code: `config/prompt_matrices.py` (duplicated in `AGENTS.md`), `schema.UserPreferences`, `YouTubeScraper.get_transcript`. Empty `README.md`. Stale `../workspace` and `../output` folders outside the repo from an earlier layout.
18. No cost/usage tracking, no eval set — you can't tell whether a model swap made outputs better or worse.

### Verdict

The *context-engineering* instincts are good (paths not payloads, isolated chunk calls, skills as files). The *control-flow* choice is the problem: it uses agents where a workflow is the right tool. Per the standard agents-vs-workflows guidance, use an LLM agent where the next step is genuinely open-ended (understanding the request, asking for missing preferences, revisions, research) and plain code where the steps are known. Today the known part (≈90% of the tokens) is agent-driven.

---

## 3. Target architecture

**"Thin agent, deterministic pipeline."** Keep DeepAgents for the conversational orchestrator (memory, skills, checkpointing, HITL come free). Move content production into one async pipeline exposed as a single tool. Share one map pass across all formats.

```
Orchestrator deep agent  (OpenRouter: tool-calling model, e.g. GLM)
  prefs injected into system prompt at start (no tool call)
  tools:
    ingest_video(url)            → cached by video_id: metadata + timestamped transcript + chunks
    produce_content(url, formats, tone, audience, purpose)
    revise(path, instructions)   → or a `reviser` subagent (genuinely agentic)
  │
  └─ produce_content  (plain async Python, no agent loop)
       1. ingest (cache hit = free)
       2. MAP   — asyncio.gather over chunks (semaphore-limited):
                  one call per chunk → ChunkDigest {title, t_start, t_end, summary,
                  key_points[], specifics[] (commands, numbers, names), quotes[]}
                  + if lecture-notes requested: that chunk's detailed notes in the same call
                  cached on disk by (video_id, chunk_idx, model, prompt_version) → resumable
       3. REDUCE — asyncio.gather over formats, one call each, input = digests (≈10–20% of transcript size):
                  blog        : coherent article from all digests
                  chapters    : summary + chapters with REAL timestamps from t_start
                  linkedin    : hook/takeaways from the whole video, not part 1
                  lecture     : merge per-chunk notes + one call for intro & Reviewer's Feedback
       4. GRADE — one structured-output grader call per format (rubric from the skill folder);
                  on fail, ONE targeted rewrite call with failing criteria; then accept + log
       5. write /workspace/<session>/<video_id>/<format>.md, return DeliverableResult[]
```

**Estimated effect** (12-chunk video, all 4 formats; estimates, verify with the usage logging in Phase 3):

| | Today | Target |
|---|---|---|
| LLM calls | ~80–100 | ~12 map + 4 reduce + 1 lecture wrap + 4 grade (+≤4 rewrites) ≈ **21–25** |
| Transcript input tokens | ~3× transcript (+ scaffolding on every agent turn) | **1×** transcript + small digests |
| Wall time | sequential chunks per format | ≈ one chunk latency + one reduce latency |
| Second request on same video | full re-run | map cached → reduce only |

Why not a LangGraph `StateGraph` for the pipeline? Not needed: the on-disk digest cache gives crash-resume for free, and plain `asyncio` is easier to test and debug. Revisit only if you need per-step human approval inside the pipeline.

### Target layout (fewer files, not more)

```
config/settings.py            provider-neutral config (model roles, limits, paths)
src/llm.py                    build_model(role) via init_chat_model("openrouter:...")  (replaces model_factory + token_budget)
src/ingest/youtube.py         scraper + yt-dlp caption fallback + video_id cache
src/pipeline/chunking.py      chapter-aware split, keeps timestamps
src/pipeline/produce.py       map / reduce / grade (async)
src/pipeline/schemas.py       ChunkDigest, DeliverableResult, VideoMetadata
src/agent/runtime.py          orchestrator
src/agent/tools.py            ingest_video, produce_content, revise + safe path helper
src/agent/middleware.py       FormatCleaner middleware
skills/<name>/SKILL.md        prompt (body) + rubric (frontmatter `rubric:` list) — one folder = one format
tests/                        wiring + pipeline tests with a fake chat model + path-guard test
evals/                        3–5 golden videos + rubric scoring script
```

---

## 4. Refactoring plan (phased; each phase ships on its own)

### Phase 0 — Security & bug fixes (½ day, do first)

1. **Path containment** for every custom tool that touches files (`generate_chunk_notes`, `merge_chunk_notes`, `read_final_output`):
   ```python
   def safe_path(virtual: str, session_id: str) -> str:
       root = os.path.realpath(Config.session_workspace_dir(session_id))
       real = os.path.realpath(os.path.join(Config.PROJECT_ROOT, virtual.lstrip("/")))
       if os.path.commonpath([real, root]) != root:
           raise ValueError(f"Path outside session workspace: {virtual}")
       return real
   ```
   Add one test: `/.env`, `../../x`, `/src/core/runtime.py` all raise.
2. **Stale parts**: write parts under `/workspace/<session>/<video_id>/` and clear `{skill}_part_*.md` at the start of a run.
3. Move `caption_entries_from_info` into `YouTubeScraper` as the transcript fallback; call `extract_info` once per video and reuse it for metadata + chapters (`functools.lru_cache` on video_id is enough).
4. Delete dead code: `config/prompt_matrices.py`, `UserPreferences`, `YouTubeScraper.get_transcript`. Delete stale `../workspace`, `../output` outside the repo (after a look). Write a real `README.md`.

### Phase 1 — Migrate Google AI Studio → OpenRouter (½–1 day)

The installed `langchain` 1.3.15 already maps the `openrouter:` prefix in `init_chat_model` to `langchain_openrouter.ChatOpenRouter`, so this is mostly deletion.

1. **Dependencies** (`requirements.txt`): remove `langchain-google-genai`, add `langchain-openrouter`. Fallback if that package misbehaves: `langchain-openai` with `ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)` — same OpenAI-compatible API.
2. **Config** (`config/settings.py`, `.env.example`): replace `GEMINI_*` with role-based models:
   ```
   OPENROUTER_API_KEY=...
   ORCHESTRATOR_MODEL=openrouter:z-ai/glm-4.6         # strongest at multi-step tool calling
   WRITER_MODEL=openrouter:deepseek/deepseek-v3.2     # reduce/long-form quality
   WORKER_MODEL=openrouter:deepseek/deepseek-v3.2     # map step: cheap, long context
   GRADER_MODEL=openrouter:z-ai/glm-4.5-air           # cheap, structured output
   LLM_RPM_LIMIT=0                                    # 0 = off; set ~20 for :free models
   LLM_MAX_RETRIES=3
   LLM_MAX_CONCURRENCY=6
   ```
   Model slugs are examples — confirm current versions and tool-calling support on openrouter.ai/models before pinning; newer DeepSeek/GLM/Qwen/Kimi releases drop in by changing one env var.
3. **Replace `model_factory.py` + `token_budget.py`** with a ~15-line `src/llm.py`:
   ```python
   from langchain.chat_models import init_chat_model
   from langchain_core.rate_limiters import InMemoryRateLimiter
   from config.settings import Config

   _limiter = InMemoryRateLimiter(requests_per_second=Config.LLM_RPM_LIMIT / 60) if Config.LLM_RPM_LIMIT else None

   def build_model(model: str, **kwargs):
       return init_chat_model(model, rate_limiter=_limiter, max_retries=Config.LLM_MAX_RETRIES, **kwargs)
   ```
   Delete `tests/test_token_budget.py`, `DEFAULT_CALL_TOKEN_ESTIMATE`, `SKILL_PROMPT_OVERHEAD_TOKENS`, `CHARS_PER_TOKEN_ESTIMATE` and the manual `acquire_tokens` call in `generate_chunk_notes`. Concurrency is bounded by an `asyncio.Semaphore(LLM_MAX_CONCURRENCY)` in the pipeline instead.
4. **OpenRouter-specific settings** (pass through the model's provider/extra-body options):
   - `provider.require_parameters=true` — only route to hosts that support tools / structured output for that model (otherwise some hosts silently ignore `tools`).
   - `provider.data_collection="deny"` if transcripts or outputs are private.
   - `models=[primary, fallback]` for automatic fallback on provider outage.
   - `usage.include=true` → per-call token counts and cost in the response, logged in Phase 3.
   - For DeepSeek hybrid-reasoning models, **disable reasoning on map/grade calls** (cost + latency); allow it only on the writer if it measurably helps. Don't use R1-style reasoning-only models as the orchestrator — weaker tool calling.
5. **Prompt caching**: DeepSeek (and several GLM hosts) cache identical prefixes automatically on OpenRouter. Keep static content first (system prompt → skill body → tone/audience) and the chunk last; the current prompt layout already does this. DeepAgents' caching middleware targets Anthropic/Bedrock/Fireworks and simply no-ops here.
6. **Chunk size**: DeepSeek/GLM have 128K–200K context and no per-minute token cap on paid keys. Keep chapter-sized chunks (quality, output-length ceiling), but `MAX_CHUNK_TOKENS` can rise to ~60–80K for chapterless videos.
7. Update `main.py`, `ui/app.py` key checks, `tests/test_runtime_wiring.py` skip condition, docstrings mentioning Gemini. `message_utils.extract_text` stays (still needed for list-of-blocks content).
8. **Acceptance**: run the same 2–3 videos through Gemini (before) and each candidate model; compare rubric pass rate, cost and latency. That's the start of `evals/`.

### Phase 2 — Pipeline restructure (2–3 days) — the main efficiency win

1. `src/pipeline/chunking.py`: keep the chapter-aware splitter, but keep `[mm:ss]` markers every ~30 s in chunk text and `t_start/t_end` per chunk (enables real timestamps).
2. `src/pipeline/produce.py`:
   - `map_chunks()` — `asyncio.gather` + semaphore, `with_structured_output(ChunkDigest)`, disk cache keyed `(video_id, idx, model, PROMPT_VERSION)`.
   - `reduce_format(skill, digests, prefs)` — one call per format; lecture-notes uses per-chunk notes + one wrap-up call.
   - `grade_and_fix(skill, text)` — structured `{passed, failing_criteria[]}`; one rewrite max; log result.
3. Expose as one orchestrator tool `produce_content(...)` returning `list[DeliverableResult]`. Remove the four writer subagents, `generate_chunk_notes`, `merge_chunk_notes`, `check_tone`, `ToneEvaluator`, `_RubricInjector` and the beta `RubricMiddleware` dependency.
4. Move each rubric into its `SKILL.md` frontmatter (`rubric:` list). One folder = one format, zero Python edits to add one.
5. Keep **one** genuinely agentic subagent: `reviser` (reads an output, applies free-form user edits, can re-run reduce for a section).
6. Inject `last_used` preferences into the orchestrator prompt at session start (read the store in Python) — drops a tool round-trip per session. Make the store namespace `("preferences", user_id)`.
7. Trim `AGENTS.md` to the new 3-tool workflow; shorter memory = fewer tokens on every orchestrator turn.

### Phase 3 — Production hardening (2–3 days)

1. **Async + streaming**: `agent.astream(..., stream_mode="updates")`; the pipeline emits progress events ("mapped 7/12 chunks", "blog graded ✓"); Streamlit renders them in `st.status`. Build the runtime once with `@st.cache_resource`.
2. **Persistence**: SQLite with WAL is fine single-user; for multi-user/hosted move to `langgraph-checkpoint-postgres` + `PostgresStore`. Add a TTL/cleanup job for old threads and workspaces.
3. **Errors**: typed errors (`TranscriptUnavailable`, `InvalidUrl`, `ProviderError`) with user-readable messages; per-call timeouts; OpenRouter model fallback list.
4. **Observability**: keep LangSmith tracing; log per-run `{video_id, formats, calls, tokens, cost_usd, latency, rubric_pass}` (cost comes from OpenRouter usage). This is what proves the refactor paid off.
5. **Tests**: pipeline tests with `langchain_core`'s fake chat models (no API key needed), path-guard test, chunking-with-timestamps test, plus an `evals/run.py` over golden videos scoring rubric pass rate per model.
6. **Packaging**: `pyproject.toml` + lock file (`uv` is already in use for `.venv`), pin `deepagents` exact.
7. Optional service layer: FastAPI `POST /jobs` + `GET /jobs/{id}` if anything other than Streamlit needs to call it.

---

## 5. Feature, subagent and tool additions

Ordered by value ÷ effort. Thanks to Phase 2, most new **formats are a single `SKILL.md` folder** reducing over the shared digests — no extra transcript cost.

**New formats (skills, near-zero code)**
- **Timestamped show notes / YouTube description** — real timestamps from digests, ready to paste.
- **X/Twitter thread**, **newsletter section**, **Medium/Substack article**.
- **SEO pack** — title variants, description, tags, keywords, thumbnail text ideas.
- **Quiz & flashcards** — MCQs + Anki-importable CSV; pairs naturally with lecture notes and exam-prep playlists.
- **Shorts/clip finder** — 30–60 s segments with start/end timestamps and a hook line per clip.
- **Translation/localization** — any output in N languages (cheap: reduce step only).

**New tools**
- `ingest_playlist(url)` — promote `extract_playlist_transcripts.py` into a tool → **course mode**: per-video notes + cross-video glossary + course outline.
- `get_video_comments(url, n)` (yt-dlp) — mine audience questions → FAQ section, "what viewers were confused about".
- `web_search(query)` (Tavily/Exa/Brave) — enrichment and fact-checking.
- `transcribe_audio(url)` — Whisper fallback (`faster-whisper` locally) for videos with no captions at all.
- `export_to(target, path)` — Notion / Google Docs / WordPress / Obsidian vault; **gate behind DeepAgents `interrupt_on` human approval** since it publishes outward.

**New subagents (genuinely agentic work)**
- **Fact-checker** — extracts claims from a draft, verifies with `web_search`, annotates or corrects. Valuable for technical/AI content where videos go stale fast.
- **Reviser** (Phase 2) — free-form edits on existing outputs.
- **Brand-voice editor** — rewrites any output against a stored voice profile under `/preferences/voice.md` (examples of the user's own posts).
- **Researcher** — "add context the video skipped": related docs, links, further reading.

**Platform features**
- Background jobs + notifications for long videos/playlists (DeepAgents `AsyncSubAgent` exists in the installed 0.7.6, or a simple job table).
- Cross-session **video cache** (transcript + digests by `video_id`) — repeat requests cost only the reduce step.
- Per-user preferences and voice profiles; usage/cost dashboard per user.
- Model A/B through `evals/` whenever OpenRouter ships a new open-weight model.

---

## 6. Suggested order

| Week | Work | Exit criterion |
|---|---|---|
| 1 | Phase 0 + Phase 1 | Path-guard test passes; same videos produce outputs on OpenRouter; Gemini code removed |
| 2 | Phase 2 | One `produce_content` call generates all 4 formats; call count and cost logged and lower than baseline |
| 3 | Phase 3 | Streaming UI, typed errors, fake-model pipeline tests, eval script |
| 4+ | Section 5 features, highest value first (show notes, quiz, playlist/course mode, fact-checker) | Each new format = one skill folder |

---

## 7. Deep Agents feature review (docs as of Oct 2026)

Installed: `deepagents 0.7.6`. Latest on PyPI: **0.7.32**. Python 3.11.3 (meets the 3.11+ requirement of the newer beta features).
Source: https://docs.langchain.com/oss/python/deepagents/overview and its subpages (subagents, async-subagents, context-engineering, event-streaming, human-in-the-loop, profiles, interpreters, skills, customization, rubric).

### 7.1 Deep Agents features in use today

| # | Feature | Where | Notes |
|---|---|---|---|
| 1 | `create_deep_agent` orchestrator (`model`, `system_prompt`, `tools`, `backend`, `store`, `skills`, `memory`, `subagents`, `permissions`, `middleware`, `checkpointer`) | `runtime.py:66` | |
| 2 | `CompositeBackend` → `FilesystemBackend(virtual_mode=True)` by default, `/preferences/` → `StoreBackend` | `runtime.py:59` | Cross-session preferences |
| 3 | `FilesystemPermission` allow/deny rules (first match wins) | `runtime.py:33` | Applies only to built-in fs tools — see Problem 11 |
| 4 | Skills (`SKILL.md`, progressive disclosure) on orchestrator **and** each subagent | `runtime.py:72`, `copywriters.py:78` | |
| 5 | Memory (`AGENTS.md`, always loaded) | `runtime.py:73` | |
| 6 | Declarative `SubAgent` dicts: `name`, `description`, `system_prompt`, `model`, `tools`, `skills`, `middleware`, `response_format` | `copywriters.py:46` | Auto-built from skill frontmatter |
| 7 | Structured subagent output (`response_format=DeliverableResult`, ≥0.5.3) | `schema.py:17` | |
| 8 | `task` tool with parallel delegation | `AGENTS.md` step 4 | |
| 9 | `RubricMiddleware` (beta, ≥0.6.5) + custom `before_agent` injector + grader tool + `on_evaluation` | `rubric_gate.py` | Injector is still needed: rubric comes only from state, and `task` seeds only `messages` |
| 10 | Custom `AgentMiddleware.wrap_tool_call` | `quality_middleware.py` | Cleans `write_file`/`edit_file` content |
| 11 | `ToolRuntime` in custom tools (reads `thread_id` from config) | `tools.py:27` | |
| 12 | LangGraph `SqliteSaver` checkpointer + `SqliteStore` | `runtime.py:43-55` | |
| 13 | *Implicit defaults*: built-in fs tools (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`), `SummarizationMiddleware`, `PatchToolCallsMiddleware`, large-tool-result offloading, the **auto-added `general-purpose` subagent**, and prompt-caching middleware | framework | Caching no-ops on Gemini. The general-purpose subagent is never used but still costs prompt tokens. |

**Not used:** `interrupt_on` / HITL, event streaming, `context_schema`, `state_schema`, harness profiles, async subagents, interpreters / programmatic tool calling (PTC), fork mode, skill tools, `pinned_skills`, `summarizer=`, multimodal reads, and LangChain prebuilt middleware (retry, fallback, call limits).

### 7.2 New features worth adopting, ranked

| Pri | Feature (min version) | Problem it fixes | How to apply here |
|---|---|---|---|
| **P0** | **Upgrade to `deepagents==0.7.32`** | Most features below need ≥0.7.13–0.7.30. Also fixes permissions being lost on middleware overrides (0.7.31) and reasoning blocks leaking into summaries (0.7.30, matters for DeepSeek's reasoning mode) | Pin the exact version. Re-run `tests/test_runtime_wiring.py`. RubricMiddleware is still beta, so re-check its state keys after upgrading. |
| **P0** | **Harness profile** — `register_harness_profile("openrouter", HarnessProfile(...))` with `excluded_tools={"glob","grep","delete"}`, `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)`, short `tool_description_overrides` | A1: ~6k tokens of scaffolding on every agent turn | Registered once in `src/llm.py` before agents are built. Applies to every agent built with an `openrouter:` model. Turning off general-purpose also stops the orchestrator delegating to an unspecialised agent that holds the transcript tools. |
| **P0** | **Set the summarisation trigger explicitly** | With no model profile, the fallback trigger is **170k tokens**. That is above DeepSeek's ~128k window, so automatic summarisation would never fire before the context overflows. | After the OpenRouter switch, check `model.profile["max_input_tokens"]`. If it is missing, set the trigger with `create_summarization_middleware` (and `summarizer=` a cheap model, ≥0.7.26). |
| **P1** | **Interpreter + Programmatic Tool Calling** — `CodeInterpreterMiddleware(ptc=["generate_chunk_notes","merge_chunk_notes"], timeout=…)` (`deepagents[quickjs]`, beta) | A1 + A3: one LLM turn per chunk, run sequentially | The writer writes one `eval` using `Promise.all(chunks.map(c => tools.generateChunkNotes(...)))`, then calls `tools.mergeChunkNotes(...)`. That is about **1 turn instead of K, and the chunks run in parallel**, with no Python rewrite. Caveats: the default `timeout` is 5 s per eval and chunk LLM calls take 20–60 s, so raise it and test whether it covers awaited tool calls; keep `max_ptc_calls` low. **Use this as the quick win if Phase 2 is deferred.** Phase 2's Python `produce_content` is still the more predictable target. PTC also fits playlist/course mode (fan out over N videos). |
| **P1** | **Event streaming v3** — `agent.astream_events(..., version="v3")`, `stream.subagents`, `stream.tool_calls`; rubric events on `stream.custom` via `CustomTransformer` | D14: Streamlit blocks for minutes behind a spinner | `st.status` shows each subagent (`started`/`completed`/`failed`), each `generate_chunk_notes` call ("chunk 7/12"), and rubric verdicts live. |
| **P1** | **`context_schema`** — `Context(session_id, user_id)` passed as `context=` on invoke and propagated to subagents | Fragile `thread_id` parsing in `_session_id`; D15: single-user preferences | Tools read `runtime.context.session_id`. Store namespace becomes `("preferences", rt.context.user_id)`. |
| **P1** | **`@dynamic_prompt` middleware** (reads `request.runtime.store`) | A6: an LLM `read_file` turn every session just to load preferences | Inject `last_used` tone/audience/purpose into the orchestrator prompt. Step 1 of `AGENTS.md` goes away. |
| **P1** | **LangChain prebuilt middleware** (already installed): `ToolRetryMiddleware`, `ModelFallbackMiddleware`, `ToolCallLimitMiddleware`, `ModelCallLimitMiddleware` | Flaky yt-dlp/transcript calls; runaway agent loops; provider outages | Retry on `get_video_*`. Cap model calls per run (for example 60). Fall back to a second OpenRouter model. |
| **P2** | **Fork-mode subagent** (`mode: "fork"`, beta, ≥0.7.13) | Revisions need the whole conversation re-described in the `task` text | The `reviser` subagent from Phase 2 inherits the conversation, so it already knows what was generated and what the user asked to change. Forks can't take `skills` or call `task`, which a reviser doesn't need. |
| **P2** | **`interrupt_on` / `FilesystemPermission(mode="interrupt")`** (≥0.6.8) | Needed once outward-facing tools exist | Gate `export_to` (Notion/WordPress/LinkedIn) behind approve/edit/reject. The SQLite checkpointer is already in place. |
| **P2** | **`state_schema`** (subclass `DeepAgentState`, ≥0.6.6) | The video manifest (video_id, chunk paths, chapter titles) lives only in message text and can be summarised away | Store it in typed state. Declarative subagents inherit the schema. |
| **P3** | **Async subagents** (≥0.7.26/0.7.30; need an Agent Protocol server, e.g. `langgraph dev` or LangSmith Deployment) | Long playlists block the chat | Only worth it if you deploy on LangGraph server instead of in-process Streamlit. Then course mode can run in the background, with `check`/`update`/`cancel`. |
| **P3** | **Multimodal `read_file`** (images/video/PDF) | — | Lets you add a thumbnail-critique/SEO skill that reads the video thumbnail. |

### 7.3 Small wins that need no new feature

- **Put each skill body straight into its writer's `system_prompt`** at build time (`read_skill_body` already exists). Each writer is currently told to `read_file` its own `SKILL.md` first, which costs one LLM turn and one tool round-trip per subagent per run. The skill file is trusted repo content, so putting it in the system prompt is safe. This also lets you drop `skills=["/skills"]` from the writer subagents, so they no longer load the whole skill catalog.
- Leave `TodoListMiddleware` off. It has been opt-in since 0.7, and this workflow doesn't need planning.
- OpenRouter/DeepSeek prompt caching is automatic and works on the prefix, so keep `AGENTS.md` and the system prompts stable. `MemoryMiddleware` already sits after caching in the stack.

### 7.4 Features to skip

- **Sandboxes / `execute`**: nothing here runs shell commands.
- **`pinned_skills`**: it is passed in invoke state, and the `task` tool doesn't forward it to subagents. Use the system-prompt approach in 7.3 instead.
- **Skill tools (`metadata.include_tools`)**: per-subagent `tools=` already scopes tools.
- **Managed Deep Agents / ACP / Deep Agents Code**: not relevant to this app.

### 7.5 Where this fits the phases

- **Phase 1** (OpenRouter): P0 upgrade, harness profile, explicit summarisation trigger.
- **Phase 2**: either the Python `produce_content` pipeline (recommended) or PTC as the lighter alternative; skill body in system prompt; fork-mode reviser; `@dynamic_prompt` preferences.
- **Phase 3**: v3 event streaming in the UI, `context_schema`/per-user store, retry/fallback/call-limit middleware, `state_schema`.
- **Phase 4**: `interrupt_on` for export tools, async subagents if you move to LangGraph server, multimodal skills.
