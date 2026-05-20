import os
from dotenv import load_dotenv
from config.settings import Config
from config.prompt_matrices import TONE_MATRICES, AUDIENCE_MATRICES, PURPOSE_MATRICES
from src.core.schema import EngineState, UserPreferences
from src.core.runtime import WorkspaceManager, DeepAgentsRuntime

def main():
    load_dotenv()
    
    if not os.getenv("GEMINI_API_KEY"):
        print("Please set GEMINI_API_KEY in your .env file.")
        return

    # Initialize runtime
    workspace_manager = WorkspaceManager(Config.WORKSPACE_DIR)
    runtime = DeepAgentsRuntime(workspace_manager)
    
    # Sample state
    state = EngineState(
        youtube_url="https://www.youtube.com/watch?v=ldqOnljDINc&t=2s", # Replace with actual URL for testing
        session_id="",
        user_prompt="I want a LinkedIn post and some detailed lecture notes.",
        preferences=UserPreferences(
            tone=TONE_MATRICES["casual"],
            audience=AUDIENCE_MATRICES["beginners"],
            purpose=PURPOSE_MATRICES["educational"]
        ),
        metadata=None,
        raw_transcript="",
        transcript_chunks=[],
        global_context="",
        planned_tasks=[],
        dynamic_outputs={},
        errors=[]
    )
    
    print("Executing pipeline...")
    final_state = runtime.execute(state)
    print(f"Execution complete. Output saved to: {os.path.join(Config.WORKSPACE_DIR, final_state.get('session_id', ''))}")
    
if __name__ == "__main__":
    main()
