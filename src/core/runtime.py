import os
import uuid
from langgraph.graph import StateGraph, END
from src.core.schema import EngineState

class WorkspaceManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def create_session_workspace(self, session_id: str) -> str:
        workspace_path = os.path.join(self.base_dir, session_id)
        os.makedirs(workspace_path, exist_ok=True)
        return workspace_path

    def write_file(self, session_id: str, filename: str, content: str):
        workspace_path = os.path.join(self.base_dir, session_id)
        file_path = os.path.join(workspace_path, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

class DeepAgentsRuntime:
    def __init__(self, workspace_manager: WorkspaceManager):
        self.workspace_manager = workspace_manager
        self.workflow = StateGraph(EngineState)
        self._build_graph()

    def _build_graph(self):
        # Define nodes
        def extract_metadata_node(state: EngineState):
            print("\n[Node: extract_metadata] Starting extraction...")
            from src.extractors.youtube_scraper import YouTubeScraper
            from src.extractors.text_splitter import TextSplitterService
            from config.settings import Config
            scraper = YouTubeScraper()
            splitter = TextSplitterService(chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP)
            try:
                state["metadata"] = scraper.get_metadata(state["youtube_url"])
                print(f"  - Title: {state['metadata'].title}")
                print(f"  - Channel: {state['metadata'].channel_name}")
                state["raw_transcript"] = scraper.get_transcript(state["metadata"].video_id)
                state["transcript_chunks"] = splitter.split_text(state["raw_transcript"])
                print(f"  - Transcript fetched ({len(state['transcript_chunks'])} chunks)")
            except Exception as e:
                print(f"  [ERROR] Extraction failed: {e}")
                state["errors"].append(f"Extraction Error: {e}")
            return state

        def plan_context_node(state: EngineState):
            if state.get("errors"): return state
            print("\n[Node: plan_context] Generating global cognitive plan...")
            from src.agents.planner import GlobalContextPlanner
            planner = GlobalContextPlanner()
            planner_output = planner.plan(
                state["raw_transcript"], 
                state["user_prompt"],
                state["preferences"].tone, 
                state["preferences"].audience, 
                state["preferences"].purpose
            )
            state["global_context"] = planner_output.global_context
            state["planned_tasks"] = planner_output.selected_skills
            print("  - Global context plan generated successfully.")
            print(f"  - Selected Skills to Execute: {state['planned_tasks']}")
            return state

        def generate_content_node(state: EngineState):
            if state.get("errors"): return state
            print("\n[Node: generate_content] Spawning sub-agents for specific formats...")
            from src.agents.copywriters import CopywriterAgent
            from src.middleware.format_cleaner import FormatCleaner

            cleaner = FormatCleaner()
            state["dynamic_outputs"] = {}

            for skill_name in state["planned_tasks"]:
                print(f"  - Running {skill_name}...")
                try:
                    agent = CopywriterAgent(skill_name)
                    raw_output = agent.generate(
                        state["raw_transcript"], 
                        state["global_context"], 
                        state["preferences"].tone, 
                        state["preferences"].audience, 
                        state["preferences"].purpose
                    )
                    state["dynamic_outputs"][skill_name] = cleaner.clean_markdown(raw_output)
                except Exception as e:
                    print(f"  [ERROR] Agent {skill_name} failed: {e}")
                    state["errors"].append(f"{skill_name} Error: {e}")

            print("  - All sub-agent generation complete and formatting cleaned.")
            return state

        def save_outputs_node(state: EngineState):
            if state.get("errors") and not state.get("dynamic_outputs"): 
                print(f"\n[Node: save_outputs] Skipping save due to errors: {state['errors']}")
                return state
            print("\n[Node: save_outputs] Writing results to workspace...")
            sid = state["session_id"]
            
            if "dynamic_outputs" in state:
                for skill_name, content in state["dynamic_outputs"].items():
                    filename = f"{skill_name}.md"
                    self.workspace_manager.write_file(sid, filename, content)
            return state
        
        self.workflow.add_node("extract_metadata", extract_metadata_node)
        self.workflow.add_node("plan_context", plan_context_node)
        self.workflow.add_node("generate_content", generate_content_node)
        self.workflow.add_node("save_outputs", save_outputs_node)
        
        self.workflow.set_entry_point("extract_metadata")
        self.workflow.add_edge("extract_metadata", "plan_context")
        self.workflow.add_edge("plan_context", "generate_content")
        self.workflow.add_edge("generate_content", "save_outputs")
        self.workflow.add_edge("save_outputs", END)
        
        self.app = self.workflow.compile()

    def execute(self, state: EngineState):
        session_id = str(uuid.uuid4())
        state["session_id"] = session_id
        if "errors" not in state:
            state["errors"] = []
        self.workspace_manager.create_session_workspace(session_id)
        
        final_state = self.app.invoke(state)
        return final_state
