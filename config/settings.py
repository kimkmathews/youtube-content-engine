import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

    # One model per role, as OpenRouter model ids (see openrouter.ai/models).
    # Swap any role by changing one env var -- every role only needs tool calling
    # (orchestrator) or structured output (worker/grader).
    # GLM-5.3-Flash is tuned for long-horizon agent/tool use -> orchestrator. DeepSeek
    # V4.1 Flash is pinned to its dated snapshot so output and rubric behaviour don't
    # shift when the floating alias moves. The grader is a different model family from
    # the writer, so it doesn't favour its own style. The fallback is a different vendor,
    # so one vendor's outage can't take down both.
    ORCHESTRATOR_MODEL = os.getenv("ORCHESTRATOR_MODEL", "z-ai/glm-5.3-flash")
    FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    WRITER_MODEL = os.getenv("WRITER_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    WORKER_MODEL = os.getenv("WORKER_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    GRADER_MODEL = os.getenv("GRADER_MODEL", "z-ai/glm-5.3-flash")

    # 0 disables client-side pacing (paid keys). ~20 for `:free` model variants.
    LLM_RPM_LIMIT = int(os.getenv("LLM_RPM_LIMIT", "0"))
    LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))
    # Parallel model calls during the map/reduce pipeline.
    LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "10"))
    # Hard cap on orchestrator model calls per user turn -- stops runaway loops.
    ORCHESTRATOR_RUN_CALL_LIMIT = int(os.getenv("ORCHESTRATOR_RUN_CALL_LIMIT", "40"))
    # Keep transcripts and outputs out of provider training data.
    OPENROUTER_DATA_COLLECTION = os.getenv("OPENROUTER_DATA_COLLECTION", "deny")
    # Many hosts serve these models at 4-bit (fp4/mxfp4/nvfp4), which is cheaper but lower
    # quality. Comma-separated allowlist; "unknown" keeps first-party/undisclosed hosts.
    OPENROUTER_QUANTIZATIONS = [q.strip() for q in os.getenv("OPENROUTER_QUANTIZATIONS", "fp8,fp16,bf16,unknown").split(",") if q.strip()]

    # Chapter-sized chunks: the models have 200K-1M token windows, but per-chapter
    # calls read better and stay well under each response's output-token ceiling.
    CHARS_PER_TOKEN_ESTIMATE = 3.5
    MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", "40000"))
    CHUNK_SIZE = int(MAX_CHUNK_TOKENS * CHARS_PER_TOKEN_ESTIMATE)
    # A timestamp marker is inserted into chunk text roughly this often, so
    # timestamped formats (chapters, show notes) can cite real times.
    TIMESTAMP_EVERY_SECONDS = 30

    # Bump when map-step prompts change, to invalidate cached chunk digests.
    PROMPT_VERSION = "1"

    PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

    # DeepAgents FilesystemBackend is rooted at PROJECT_ROOT in virtual_mode, so the
    # agent sees stable virtual paths like "/skills", "/memory", "/workspace".
    SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")
    MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
    WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, "workspace")
    # Cross-session cache of ingested videos and chunk digests, keyed by content hash.
    CACHE_DIR = os.path.join(WORKSPACE_ROOT, "_cache")

    DB_PATH = os.path.join(PROJECT_ROOT, "state.db")
    # Separate sqlite file for the cross-session preferences store -- distinct from
    # DB_PATH's per-thread checkpoints so the two `.setup()` migrations never share
    # a connection/schema.
    STORE_DB_PATH = os.path.join(PROJECT_ROOT, "preferences.db")

    @classmethod
    def session_workspace_dir(cls, session_id: str) -> str:
        """Real (non-virtual) path to a session's isolated workspace directory."""
        path = os.path.join(cls.WORKSPACE_ROOT, session_id)
        os.makedirs(path, exist_ok=True)
        return path

    @classmethod
    def ensure_workspace(cls):
        for path in (cls.WORKSPACE_ROOT, cls.CACHE_DIR, cls.SKILLS_DIR, cls.MEMORY_DIR):
            os.makedirs(path, exist_ok=True)


Config.ensure_workspace()
