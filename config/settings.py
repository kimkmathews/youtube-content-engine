import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MODEL_NAME = "gemma-4-31b-it"
    SUBAGENT_MODEL_NAME = "gemma-4-31b-it"  # More capable model for complex copy tasks
    
    # Text Splitter Config
    CHUNK_SIZE = 4000
    CHUNK_OVERLAP = 500

    # Workspace directory relative to project root
    WORKSPACE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "state.db")
    @classmethod
    def ensure_workspace(cls):
        os.makedirs(cls.WORKSPACE_DIR, exist_ok=True)

Config.ensure_workspace()
