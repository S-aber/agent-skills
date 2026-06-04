import uuid
import json
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Boolean, func
from sqlalchemy.dialects.sqlite import CHAR
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class MCPServer(Base):
    """MCP server record — like Skill model, stores an uploaded MCP server package."""

    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(
        CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str | None] = mapped_column(
        CHAR(36), nullable=True, index=True
    )
    uploader_id: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="private")  # private | public
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    command: Mapped[str] = mapped_column(String(500), nullable=False)
    args: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON array
    folder_path: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    @property
    def args_list(self) -> list[str]:
        return json.loads(self.args) if self.args else []
