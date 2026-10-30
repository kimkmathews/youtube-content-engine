"""Agent wiring tests: catch wiring bugs without calling OpenRouter.

They check that the skill catalog is valid, that the graph builds with the OpenRouter
harness profile applied, and that a full orchestrator turn (tool call -> answer)
streams correctly with a scripted fake model. Generation quality needs a live key
and the eval script, not unit tests.
"""

import os
import unittest
from unittest import mock

# Set before anything loads .env: keeps test runs out of LangSmith (tracing would also
# serialise -- and exhaust -- the scripted fake model's message iterator).
os.environ["LANGSMITH_TRACING"] = os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-not-used")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from config.settings import Config
from src.core.skill_files import STRATEGIES, load_skills


class ScriptedModel(GenericFakeChatModel):
    """Fake chat model that reports itself as an OpenRouter model (so the OpenRouter
    harness profile applies) and records the tool names bound on each call."""

    bound_tools: list = []

    def _get_ls_params(self, stop=None, **kwargs):
        return {**super()._get_ls_params(stop=stop, **kwargs), "ls_provider": "openrouter"}

    def bind_tools(self, tools, **kwargs):
        self.bound_tools.append({getattr(t, "name", None) or t.get("name") for t in tools})
        return self


class TestSkillCatalog(unittest.TestCase):
    def test_every_skill_is_valid(self):
        skills = load_skills()
        self.assertEqual(
            sorted(skills),
            ["blog-writer", "chapter-generator", "lecture-notes", "linkedin-specialist",
             "quiz-flashcards", "seo-pack", "show-notes", "x-thread"],
        )
        names = {s.output_file for s in skills.values()}
        self.assertEqual(len(names), len(skills), "output_file names must be unique")
        for entry in os.listdir(Config.SKILLS_DIR):
            self.assertIn(entry, skills, f"{entry}: frontmatter name must match its directory")
        for skill in skills.values():
            self.assertIn(skill.strategy, STRATEGIES)
            self.assertTrue(skill.rubric, f"{skill.name}: needs a rubric")
            self.assertTrue(skill.body)


class TestAgentGraph(unittest.TestCase):
    def _runtime(self, model=None):
        from src.core import runtime

        if model is None:
            return runtime.DeepAgentsRuntime()
        with mock.patch.object(runtime, "build_model", lambda model_id, temperature=None: model):
            return runtime.DeepAgentsRuntime()

    def test_model_timeout_is_seconds_not_milliseconds(self):
        from src.core.llm import build_model

        self.assertEqual(build_model(Config.WORKER_MODEL).request_timeout, Config.LLM_TIMEOUT_SECONDS * 1000)

    def test_graph_builds_with_real_openrouter_models(self):
        agent = self._runtime().agent
        tools = set(agent.nodes["tools"].bound.tools_by_name)
        self.assertTrue({"ingest_video", "produce_content", "task"} <= tools, tools)

    def test_full_turn_streams_tool_call_and_answer(self):
        from src.core import tools as tools_module

        scripted = ScriptedModel(messages=iter([
            AIMessage(content="", tool_calls=[{"name": "ingest_video", "args": {"url": "https://youtu.be/abcdefghijk"}, "id": "c1"}]),
            AIMessage(content="It's a 2-minute video. Which formats?"),
        ]))
        fake_ingest = mock.Mock(return_value=mock.Mock(
            metadata=mock.Mock(title="Demo", channel_name="Chan", length_seconds=120),
            transcript_language="English", chapters_detected=False, chunks=[],
        ))
        with mock.patch.object(tools_module.produce, "ingest", fake_ingest):
            events = list(self._runtime(scripted).stream("test-session", "Summarise https://youtu.be/abcdefghijk"))

        fake_ingest.assert_called_once()
        self.assertIn(("tool", "ingest_video"), events)
        # OpenRouter harness profile: unused fs tools are hidden from the model, and the
        # general-purpose subagent is off (task lists only the reviser).
        seen = scripted.bound_tools[0]
        self.assertTrue({"ingest_video", "produce_content", "read_file", "task"} <= seen, seen)
        self.assertTrue({"glob", "grep", "delete", "execute"}.isdisjoint(seen), seen)
        self.assertEqual(events[-1], ("answer", "It's a 2-minute video. Which formats?"))


if __name__ == "__main__":
    unittest.main()
