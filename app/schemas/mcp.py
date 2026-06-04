from pydantic import BaseModel, Field
from datetime import datetime


class MCPServerResponse(BaseModel):
    id: str
    workspace_id: str | None = None
    uploader_id: str
    source: str
    name: str
    description: str
    command: str
    args: list[str]
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MCPServerToggleResponse(BaseModel):
    id: str
    name: str
    enabled: bool
