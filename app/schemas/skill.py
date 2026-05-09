from pydantic import BaseModel
from datetime import datetime


class SkillResponse(BaseModel):
    id: str
    workspace_id: str | None = None
    uploader_id: str
    source: str
    name: str
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int


class SkillContentResponse(BaseModel):
    id: str
    name: str
    description: str
    content: str  # full SKILL.md content
    source: str
