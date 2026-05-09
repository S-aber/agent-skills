from pydantic import BaseModel, Field
from datetime import datetime


class CreateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    activated_skill_ids: list[str] = Field(default_factory=list, max_length=20)
    model_id: str = Field(..., min_length=1)


class ConversationResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    activated_skill_ids: list[str]
    model_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    conversations: list[ConversationResponse]
    total: int
