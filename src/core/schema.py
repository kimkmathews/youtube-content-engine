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

