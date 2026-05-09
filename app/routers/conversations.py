import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.services.auth_service import get_current_user
from app.schemas.conversation import CreateConversationRequest, ConversationResponse

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    req: CreateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(req.activated_skill_ids) > 20:
        raise HTTPException(status_code=400, detail="激活 Skill 数量不能超过 20 个")

    conv = Conversation(
        workspace_id=current_user.id,
        title=req.title,
        activated_skill_ids=json.dumps(req.activated_skill_ids),
        model_id=req.model_id,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    return ConversationResponse(
        id=conv.id,
        workspace_id=conv.workspace_id,
        title=conv.title,
        activated_skill_ids=json.loads(conv.activated_skill_ids),
        model_id=conv.model_id,
        created_at=conv.created_at,
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.workspace_id == current_user.id)
        .order_by(Conversation.created_at.desc())
    )
    convs = result.scalars().all()
    return [
        ConversationResponse(
            id=c.id,
            workspace_id=c.workspace_id,
            title=c.title,
            activated_skill_ids=json.loads(c.activated_skill_ids),
            model_id=c.model_id,
            created_at=c.created_at,
        )
        for c in convs
    ]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "会话不存在"})

    return ConversationResponse(
        id=conv.id,
        workspace_id=conv.workspace_id,
        title=conv.title,
        activated_skill_ids=json.loads(conv.activated_skill_ids),
        model_id=conv.model_id,
        created_at=conv.created_at,
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "会话不存在"})

    # Delete associated messages first
    from app.models.message import Message
    msg_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
    )
    for msg in msg_result.scalars().all():
        await db.delete(msg)

    await db.delete(conv)
    await db.commit()
    return {"ok": True}
