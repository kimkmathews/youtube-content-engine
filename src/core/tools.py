import os
import re
from langchain_core.tools import tool
from config.settings import Config
from src.extractors.youtube_scraper import YouTubeScraper
from src.core.schema import VideoMetadata

@tool
def get_video_metadata(url: str) -> dict:
    """Extracts metadata (title, channel, description, duration) from a YouTube URL."""
    print(f"\n[Tool] Extracting metadata for: {url}")
    scraper = YouTubeScraper()
    metadata = scraper.get_metadata(url)
    return metadata.model_dump()

@tool
def get_video_transcript(video_id: str) -> str:
    """Extracts the raw transcript for a given YouTube video ID."""
    print(f"\n[Tool] Extracting transcript for video ID: {video_id}")
    scraper = YouTubeScraper()
    return scraper.get_transcript(video_id)

@tool
def get_available_skills() -> str:
    """Lists the available content generation skills and their descriptions. Call this to know what skills you can run."""
    print("\n[Tool] Checking available skills...")
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
    if not os.path.exists(skills_dir):
        # Fallback to project root skills folder if any
        skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills")
        
    skills_info = []
    if not os.path.exists(skills_dir):
        return "No skills found."
    for filename in os.listdir(skills_dir):
        if filename.endswith(".md"):
            filepath = os.path.join(skills_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
                if match:
                    skills_info.append(match.group(1).strip())
                else:
                    skills_info.append(f"name: {filename.replace('.md', '')}\ndescription: No description provided.")
    return "\n\n".join(skills_info)

@tool
def run_copywriter_skill(skill_name: str, transcript: str, global_context: str, tone: str, audience: str, purpose: str, output_filename: str) -> str:
    """Runs a specific copywriter skill (e.g., 'linkedin_specialist') using a dedicated subagent and saves the result to the workspace."""
    from src.agents.copywriters import run_skill_agent
    
    print(f"\n[Tool] Spawning subagent for skill: {skill_name} ...")
    
    try:
        result = run_skill_agent(skill_name, transcript, global_context, tone, audience, purpose)
        
        workspace = Config.WORKSPACE_DIR
        filepath = os.path.join(workspace, output_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(result)
            
        return f"Content generated and saved successfully to {filepath}"
    except Exception as e:
        return f"Failed to run skill {skill_name}: {str(e)}"

@tool
def list_workspace_files() -> str:
    """Lists files in the workspace (output directory)."""
    print("\n[Tool] Listing workspace files...")
    workspace = Config.WORKSPACE_DIR
    if not os.path.exists(workspace):
        return "Workspace empty."
    return "\n".join(os.listdir(workspace))

@tool
def read_workspace_file(filename: str) -> str:
    """Reads a file from the workspace."""
    print(f"\n[Tool] Reading file: {filename}")
    filepath = os.path.join(Config.WORKSPACE_DIR, filename)
    if not os.path.exists(filepath):
        return f"File {filename} not found."
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

@tool
def write_workspace_file(filename: str, content: str) -> str:
    """Writes content to a file in the workspace."""
    print(f"\n[Tool] Writing to file: {filename}")
    filepath = os.path.join(Config.WORKSPACE_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Successfully wrote to {filename}"

