"""Chat model construction for every role in the app, via OpenRouter.

Replaces the Gemini free-tier token-budget machinery: a paid OpenRouter key has
no per-minute token cap, so pacing is optional (LLM_RPM_LIMIT) and concurrency is
bounded where the fan-out happens (the pipeline's max_concurrency).
"""

import threading

from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openrouter import ChatOpenRouter

from config.settings import Config

_rate_limiter = InMemoryRateLimiter(requests_per_second=Config.LLM_RPM_LIMIT / 60) if Config.LLM_RPM_LIMIT else None

# require_parameters: only route to upstream hosts that support every parameter we
# send (tools, response_format) -- otherwise some silently ignore them. Azure is
# excluded for the same multi-turn reasoning-replay reason deepagents' own
# OpenRouter profile gives.
_PROVIDER_PREFS = {
    "require_parameters": True,
    "data_collection": Config.OPENROUTER_DATA_COLLECTION,
    "ignore": ["azure"],
}
if Config.OPENROUTER_QUANTIZATIONS:
    _PROVIDER_PREFS["quantizations"] = Config.OPENROUTER_QUANTIZATIONS


def build_model(model_id: str, temperature: float | None = None) -> ChatOpenRouter:
    kwargs = {
        "model": model_id,
        "max_retries": Config.LLM_MAX_RETRIES,
        "timeout": Config.LLM_TIMEOUT_SECONDS * 1000,  # ChatOpenRouter's timeout is in milliseconds
        "openrouter_provider": _PROVIDER_PREFS,
        "app_title": "YouTube Content Engine",
        "rate_limiter": _rate_limiter,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    return ChatOpenRouter(**kwargs)


# Slims the DeepAgents harness for every agent on an OpenRouter model: this app has no
# use for search/delete/shell tools, and the auto-added general-purpose subagent would
# only duplicate the orchestrator (with its tools) at the cost of prompt tokens.
register_harness_profile(
    "openrouter",
    HarnessProfile(
        excluded_tools=frozenset({"glob", "grep", "delete", "execute"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)


class UsageTracker(BaseCallbackHandler):
    """Sums calls, tokens and OpenRouter-reported cost across one pipeline run."""

    def __init__(self):
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self._lock = threading.Lock()

    def on_llm_end(self, response, **kwargs) -> None:
        for generations in response.generations:
            for gen in generations:
                message = getattr(gen, "message", None)
                if message is None:
                    continue
                usage = getattr(message, "usage_metadata", None) or {}
                cost = (getattr(message, "response_metadata", None) or {}).get("cost") or 0.0
                with self._lock:
                    self.calls += 1
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)
                    self.cost_usd += float(cost)

    def summary(self) -> str:
        return (
            f"{self.calls} model calls, {self.input_tokens:,} input / {self.output_tokens:,} output tokens, "
            f"${self.cost_usd:.4f}"
        )
