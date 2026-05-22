import os
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import Config
import time
import os
import re
from deepagents import create_deep_agent
from config.settings import Config

def run_skill_agent(skill_name: str, transcript: str, global_context: str, tone: str, audience: str, purpose: str) -> str:
    skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills")
    filepath = os.path.join(skills_dir, f"{skill_name}.md")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Skill file not found: {filepath}")
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Remove the frontmatter block
    content = re.sub(r'^---\s*\n.*?\n---\n', '', content, flags=re.DOTALL | re.MULTILINE)
    
    system_prompt = content.format(
        tone=tone,
        audience=audience,
        purpose=purpose,
        global_context=global_context,
        transcript=transcript
    )
    
    agent = create_deep_agent(
        model=f"google_genai:{Config.SUBAGENT_MODEL_NAME}",
        system_prompt=system_prompt,
        tools=[] 
    )
    
    print(f"  [Subagent] {skill_name} is generating content...")
    # We invoke it with a single user message to trigger generation
    response = agent.invoke({"messages": [{"role": "user", "content": "Please execute your task based on the instructions and transcript."}]})
    time.sleep(5)
    print(f"  [Subagent] {skill_name} completed generation.")
    
    content = response["messages"][-1].content
    if isinstance(content, list):
        text_blocks = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(text_blocks) if text_blocks else str(content)
    return content
