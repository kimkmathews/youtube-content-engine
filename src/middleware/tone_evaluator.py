from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from config.settings import Config

class ToneEvaluator:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=Config.MODEL_NAME,
            temperature=0.1,
        )
        self.prompt = PromptTemplate.from_template(
            """You are a QA Tone Evaluator.
Review the following drafted content and determine if it strictly adheres to the required tone: '{target_tone}'.

Drafted Content:
{content}

Respond strictly with 'PASS' if the tone matches. If it fails, respond with 'FAIL' followed by a short 1-sentence reason why.
"""
        )

    def evaluate(self, content: str, target_tone: str) -> bool:
        chain = self.prompt | self.llm
        response = chain.invoke({
            "content": content[:3000], # Evaluate based on first 3000 chars to save tokens
            "target_tone": target_tone
        })
        result = response.content.strip().upper()
        return result.startswith("PASS")
