import os
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import Config

class CopywriterAgent:
    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        self.llm = ChatGoogleGenerativeAI(
            model=Config.MODEL_NAME,
            temperature=0.7, # Higher temperature for creative copy
        )
        self.skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills")

    def _load_skill_prompt(self, tone: str, audience: str, purpose: str, global_context: str, transcript: str) -> str:
        filepath = os.path.join(self.skills_dir, f"{self.skill_name}.md")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Skill file not found: {filepath}")
            
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Remove the frontmatter block
        content = re.sub(r'^---\s*\n.*?\n---\n', '', content, flags=re.DOTALL | re.MULTILINE)
        
        # Format the template with variables
        formatted_prompt = content.format(
            tone=tone,
            audience=audience,
            purpose=purpose,
            global_context=global_context,
            transcript=transcript
        )
        return formatted_prompt

    def generate(self, transcript: str, global_context: str, tone: str, audience: str, purpose: str) -> str:
        system_prompt = self._load_skill_prompt(tone, audience, purpose, global_context, transcript)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Please execute your task based on the instructions and transcript.")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
