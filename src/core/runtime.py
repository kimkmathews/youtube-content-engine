import sqlite3
import time
from langgraph.checkpoint.sqlite import SqliteSaver
from deepagents import create_deep_agent
from config.settings import Config
from src.core.tools import (
    get_video_metadata,
    get_video_transcript,
    get_available_skills,
    run_copywriter_skill,
    list_workspace_files,
    read_workspace_file,
    write_workspace_file
)

class DeepAgentsRuntime:
    def __init__(self):
        # Create sqlite connection for memory
        self.conn = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conn)
        
        system_prompt = """You are the Global Context Planner and Orchestrator for the YouTube Content Engine.
Your goal is to manage the end-to-end process of generating content from YouTube videos based on user requests.

Capabilities:
1. Extract video metadata and transcript using `get_video_metadata` and `get_video_transcript`.
2. Check available content generation skills using `get_available_skills`.
3. Run specific subagents to generate content using `run_copywriter_skill`.
4. Read and modify files in the workspace using `list_workspace_files`, `read_workspace_file`, and `write_workspace_file`.

Workflow:
- When a user provides a YouTube URL and instructions, first extract the metadata and transcript.
- Formulate a cognitive plan based on the transcript and user instructions.
- Execute the required skills (e.g., blog_writer, linkedin_specialist) passing the necessary context and tone/audience parameters.
- Review and refine the output if requested by the user, directly modifying workspace files.
"""

        tools = [
            get_video_metadata,
            get_video_transcript,
            get_available_skills,
            run_copywriter_skill,
            list_workspace_files,
            read_workspace_file,
            write_workspace_file
        ]
        
        self.agent = create_deep_agent(
            model=f"google_genai:{Config.MODEL_NAME}",
            system_prompt=system_prompt,
            tools=tools,
            checkpointer=self.checkpointer
        )

    def invoke(self, session_id: str, user_message: str):
        config = {"configurable": {"thread_id": session_id}}
        response = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_message}]},
            config=config
        )
        content = response["messages"][-1].content
        time.sleep(5)
        
        if isinstance(content, list):
            text_blocks = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
            return "\n".join(text_blocks) if text_blocks else str(content)
        return content
