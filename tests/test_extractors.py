import unittest
from src.extractors.youtube_scraper import YouTubeScraper
from src.extractors.text_splitter import TextSplitterService

class TestExtractors(unittest.TestCase):
    def setUp(self):
        self.scraper = YouTubeScraper()
        self.splitter = TextSplitterService(chunk_size=100, chunk_overlap=10)

    def test_extract_video_id(self):
        url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        url2 = "https://youtu.be/dQw4w9WgXcQ"
        
        self.assertEqual(self.scraper.extract_video_id(url1), "dQw4w9WgXcQ")
        self.assertEqual(self.scraper.extract_video_id(url2), "dQw4w9WgXcQ")

    def test_text_splitter(self):
        text = "This is a very long string that we need to split. " * 10
        chunks = self.splitter.split_text(text)
        self.assertTrue(len(chunks) > 1)
        self.assertTrue(len(chunks[0]) <= 100)

if __name__ == '__main__':
    unittest.main()
