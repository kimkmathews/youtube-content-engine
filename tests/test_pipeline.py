"""End-to-end pipeline test with fake models and a fake video: no API key, no network."""

import os
import tempfile
import threading
import unittest
from unittest import mock

from langchain_core.messages import AIMessage

from config.settings import Config
from src.core.schema import Chunk, ChunkDigest, Criterion, GradeResult, UserPreferences, VideoMetadata
from src.pipeline import produce


class FakeModel:
    """Stands in for ChatOpenRouter: plain invoke() and with_structured_output()."""

    def __init__(self, fail_first_grades: int = 0):
        self.calls = []
        self.fail_first_grades = fail_first_grades
        self._lock = threading.Lock()

    def invoke(self, messages, config=None):
        with self._lock:
            self.calls.append("text")
        return AIMessage(content="## Section\n\nWritten body.")

    def with_structured_output(self, schema):
        model = self

        class _Structured:
            def invoke(self, messages, config=None):
                with model._lock:
                    model.calls.append(schema.__name__)
                    if schema is GradeResult:
                        passed = model.fail_first_grades <= 0
                        model.fail_first_grades -= 1
                        return GradeResult(criteria=[Criterion(criterion="c1", passed=passed, gap="" if passed else "missing x")])
                if schema is ChunkDigest:
                    return ChunkDigest(title="T", start_timestamp="00:00", summary="s", key_points=["k"], specifics=[], notable_moments=[])
                return schema(introduction="# Title\n\nOverview.", closing="## Reviewer's Feedback\n\nGood.")

        return _Structured()


def _video():
    return produce.Ingested(
        metadata=VideoMetadata(video_id="vid12345678", title="Demo", channel_name="Chan", description="", length_seconds=120),
        transcript_language="English",
        chapters_detected=True,
        chunks=[
            Chunk(index=1, title="Intro", start=0, end=60, text="[00:00] hello"),
            Chunk(index=2, title="Main", start=60, end=120, text="[01:00] world"),
        ],
    )


class TestProduce(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.patches = [
            mock.patch.object(Config, "PROJECT_ROOT", root),
            mock.patch.object(Config, "WORKSPACE_ROOT", os.path.join(root, "workspace")),
            mock.patch.object(Config, "CACHE_DIR", os.path.join(root, "workspace", "_cache")),
            mock.patch.object(produce, "ingest", lambda url: _video()),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def _run(self, formats, worker, writer, grader):
        models = {Config.WORKER_MODEL: worker, Config.WRITER_MODEL: writer, Config.GRADER_MODEL: grader}
        with mock.patch.object(produce, "build_model", lambda model_id, temperature=None: models[model_id]):
            return produce.produce("https://youtu.be/vid12345678", formats, UserPreferences(), "s1")

    def test_reduce_and_per_chunk_formats(self):
        # One fake plays every role.
        fake = FakeModel()
        results, _usage = self._run(["blog-writer", "lecture-notes"], fake, fake, fake)

        self.assertEqual([r.skill_name for r in results], ["blog-writer", "lecture-notes"])
        self.assertTrue(all(r.passed_rubric for r in results))
        # 2 digests + 1 blog + (2 sections + 1 bookends) for lecture notes + 2 grades
        self.assertEqual(fake.calls.count("ChunkDigest"), 2)
        self.assertEqual(fake.calls.count("text"), 3)
        self.assertEqual(fake.calls.count("Bookends"), 1)
        self.assertEqual(fake.calls.count("GradeResult"), 2)

        lecture = os.path.join(Config.WORKSPACE_ROOT, "s1", "vid12345678", "lecture_notes.md")
        with open(lecture, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("# Title"))
        # Section headings come from the real chapter titles (set in code), and the model's
        # own heading is dropped -- so exactly one H2 per chapter.
        self.assertEqual([l for l in text.splitlines() if l.startswith("## ")][:2], ["## Intro", "## Main"])
        self.assertNotIn("## Section", text)
        self.assertEqual(text.count("Reviewer's Feedback"), 1)
        self.assertTrue(os.path.isfile(os.path.join(Config.WORKSPACE_ROOT, "s1", "vid12345678", "transcript.md")))

    def test_failed_grade_triggers_one_rewrite_and_regrade(self):
        fake = FakeModel(fail_first_grades=1)
        results, _ = self._run(["blog-writer"], fake, fake, fake)
        self.assertTrue(results[0].passed_rubric)
        self.assertEqual(fake.calls.count("GradeResult"), 2)
        self.assertEqual(fake.calls.count("text"), 2)  # draft + rewrite

    def test_digests_are_cached_across_runs(self):
        fake = FakeModel()
        self._run(["seo-pack"], fake, fake, fake)
        fake.calls.clear()
        self._run(["x-thread"], fake, fake, fake)
        self.assertEqual(fake.calls.count("ChunkDigest"), 0)

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(ValueError):
            self._run(["podcast"], FakeModel(), FakeModel(), FakeModel())


if __name__ == "__main__":
    unittest.main()
