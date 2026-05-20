import os
import re
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from config.settings import Config

class PlannerOutput(BaseModel):
    global_context: str = Field(description="The global cognitive plan outlining core messages and style constraints.")
    selected_skills: List[str] = Field(description="The list of skill names selected to execute.")

class GlobalContextPlanner:
    def __init__(self):
        # Using structured output to force the LLM to return the JSON schema
        self.llm = ChatGoogleGenerativeAI(
            model=Config.MODEL_NAME,
            temperature=0.2,
        ).with_structured_output(PlannerOutput)
        self.skills_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "skills")

    def _get_available_skills(self) -> str:
        skills_info = []
        if not os.path.exists(self.skills_dir):
            return "No skills found."
        for filename in os.listdir(self.skills_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(self.skills_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extract frontmatter between ---
                    match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
                    if match:
                        skills_info.append(match.group(1).strip())
                    else:
                        skills_info.append(f"name: {filename.replace('.md', '')}\ndescription: No description provided.")
        return "\n\n".join(skills_info)

    def plan(self, transcript_sample: str, user_prompt: str, tone: str, audience: str, purpose: str) -> PlannerOutput:
        available_skills = self._get_available_skills()
        
        prompt = PromptTemplate.from_template(
            """You are a Global Context Planner for a content engine.
Your goal is to analyze the provided raw video transcript and the user's specific prompt, then generate a high-level structural outline and select the appropriate skills to execute.

Available Skills to choose from:
{available_skills}

User Prompt:
{user_prompt}

User Preferences:
- Tone: {tone}
- Audience: {audience}
- Purpose: {purpose}

Raw Transcript (first part):
{transcript_sample}

Generate a concise global context plan outlining the core message and style constraints, AND select the EXACT skill names from the available skills list that best fulfill the User Prompt.
"""
        )
        
        chain = prompt | self.llm
        response = chain.invoke({
            "available_skills": available_skills,
            "user_prompt": user_prompt,
            "transcript_sample": transcript_sample[:15000], # Send a safe chunk to establish context
            "tone": tone,
            "audience": audience,
            "purpose": purpose
        })
        return response
