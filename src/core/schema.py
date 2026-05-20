from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class VideoMetadata(BaseModel):
    video_id: str
    title: str
    channel_name: str
    description: str
    length_seconds: int

class UserPreferences(BaseModel):
    tone: str = "casual"
    audience: str = "beginners"
    purpose: str = "educational"

class EngineState(TypedDict):
    youtube_url: str
    session_id: str
    preferences: UserPreferences
    
    # Extraction Layer
    metadata: Optional[VideoMetadata]
    raw_transcript: str
    transcript_chunks: List[str]
    
    # Planning Layer
    global_context: str
    
    # Dynamic Orchestration
    user_prompt: str
    planned_tasks: List[str]
    dynamic_outputs: Dict[str, str]
    
    # System
    errors: List[str]
