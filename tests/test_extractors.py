import unittest
from types import SimpleNamespace

from src.extractors.youtube_scraper import YouTubeScraper
from src.pipeline.chunking import build_chunks


def _entries(n, step=10.0):
    return [SimpleNamespace(text=f"line {i}", start=i * step, duration=step) for i in range(n)]


class TestExtractors(unittest.TestCase):
    def test_extract_video_id(self):
        scraper = YouTubeScraper()
        self.assertEqual(scraper.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(scraper.extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        with self.assertRaises(ValueError):
            scraper.extract_video_id("https://example.com/not-youtube")

    def test_description_chapters(self):
        chapters = YouTubeScraper()._parse_description_chapters("00:00 Intro\n01:30 Setup\n1:02:03 Deploy")
        self.assertEqual([c["start"] for c in chapters], [0.0, 90.0, 3723.0])
        self.assertEqual(chapters[1]["end"], 3723.0)
        self.assertIsNone(chapters[-1]["end"])


class TestChunking(unittest.TestCase):
    def test_chapters_keep_titles_intro_and_timestamps(self):
        chapters = [{"start": 20.0, "end": 60.0, "title": "Setup"}, {"start": 60.0, "end": None, "title": "Deploy"}]
        chunks = build_chunks(_entries(10), chapters)
        self.assertEqual([c.title for c in chunks], ["Intro", "Setup", "Deploy"])
        self.assertEqual([c.start for c in chunks], [0.0, 20.0, 60.0])
        self.assertTrue(chunks[1].text.startswith("[00:20] line 2"))
        self.assertEqual([c.index for c in chunks], [1, 2, 3])

    def test_oversized_section_splits_on_entry_boundaries(self):
        chunks = build_chunks(_entries(50), None, max_chars=100)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(c.title is None for c in chunks))
        # Consecutive chunks are contiguous in time: nothing dropped, nothing duplicated.
        for a, b in zip(chunks, chunks[1:]):
            self.assertEqual(a.end, b.start)

    def test_long_chapter_parts_are_labelled(self):
        chunks = build_chunks(_entries(50), [{"start": 0.0, "end": None, "title": "Talk"}], max_chars=100)
        self.assertTrue(chunks[0].title.startswith("Talk (part 1/"))


if __name__ == '__main__':
    unittest.main()
