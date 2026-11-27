from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

Tone = Literal["technical", "casual", "professional"]
Audience = Literal["beginners", "experts", "c_suite"]
Purpose = Literal["educational", "promotional", "entertainment"]


@dataclass
class Context:
    """Per-run runtime context (`context_schema`), propagated to tools and subagents."""

    session_id: str
    user_id: str = "local"


class VideoMetadata(BaseModel):
    video_id: str
    title: str
    channel_name: str
    description: str
    length_seconds: int


class UserPreferences(BaseModel):
    tone: Tone = "casual"
    audience: Audience = "beginners"
    purpose: Purpose = "educational"
    language: str = "English"


class Chunk(BaseModel):
    index: int
    title: str | None
    start: float
    end: float | None
    text: str


class ChunkDigest(BaseModel):
    """Compact, format-neutral notes on one transcript chunk -- the shared map-step output
    every format reduces from, so the transcript is only read once per video."""

    title: str = Field(description="The section's real topic (use the given chapter title if one was given)")
    start_timestamp: str = Field(description="Timestamp where this section starts, e.g. '12:05', taken from the [mm:ss] markers")
    summary: str = Field(description="3-6 sentence summary of what this section covers")
    key_points: list[str] = Field(description="The main ideas, each a full sentence")
    specifics: list[str] = Field(description="Concrete details worth preserving verbatim: commands, names, numbers, examples, caveats")
    notable_moments: list[str] = Field(description="'[mm:ss] description' entries for quotable or clip-worthy moments")


class Criterion(BaseModel):
    criterion: str
    passed: bool
    gap: str = Field(default="", description="If failed: what specifically is missing or wrong")


class GradeResult(BaseModel):
    criteria: list[Criterion]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.criteria)

    @property
    def failing(self) -> list[Criterion]:
        return [c for c in self.criteria if not c.passed]


class DeliverableResult(BaseModel):
    output_path: str = Field(description="Full workspace path to the generated file")
    skill_name: str
    passed_rubric: bool
    failing_criteria: list[str] = []
