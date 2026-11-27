import os
import unittest

from config.settings import Config
from src.core.workspace import safe_path


class TestSafePath(unittest.TestCase):
    def test_allows_paths_inside_the_session_workspace(self):
        real = safe_path("/workspace/s1/vid/blog.md", "s1")
        self.assertEqual(real, os.path.realpath(os.path.join(Config.WORKSPACE_ROOT, "s1", "vid", "blog.md")))

    def test_rejects_escapes(self):
        for bad in ["/.env", "/src/core/runtime.py", "/workspace/s1/../../.env", "/workspace/other/blog.md", "../../x"]:
            with self.subTest(path=bad), self.assertRaises(ValueError):
                safe_path(bad, "s1")


if __name__ == "__main__":
    unittest.main()
