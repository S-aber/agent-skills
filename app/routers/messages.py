import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.auth_service import get_current_user
from app.services.agent_service import run_agent
from app.schemas.message import SendMessageRequest, MessageResponse

router = APIRouter(prefix="/api/v1/conversations", tags=["messages"])


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and stream the response via SSE."""
    # Verify conversation ownership
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "会话不存在"})

    async def sse_generator():
        async for sse_event in run_agent(db, conv, req.content):
            yield sse_event

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: str,
    limit: int = 50,
    before: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List messages in a conversation (paginated)."""
    # Verify ownership
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "会话不存在"})

    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )

    if before:
        query = query.where(Message.created_at < before)

    result = await db.execute(query)
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            tool_calls=json.loads(m.tool_calls) if m.tool_calls else None,
            created_at=m.created_at,
        )
        for m in messages
    ]
