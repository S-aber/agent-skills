import os
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.models.conversation import Conversation
from app.services.auth_service import get_current_user
from app.config import get_settings
from app.schemas.upload import UploadedFileInfo
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])

settings = get_settings()


def _get_upload_dir(conversation_id: str) -> str:
    return os.path.join(settings.uploads_storage_path, conversation_id)


@router.post("")
async def upload_file(
    conversation_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file for use in a conversation."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "会话不存在"},
        )

    upload_dir = _get_upload_dir(conversation_id)
    os.makedirs(upload_dir, exist_ok=True)

    filename = file.filename or "unnamed"
    dest = os.path.join(upload_dir, filename)

    # Avoid overwriting: add timestamp before extension on conflict
    if os.path.exists(dest):
        name, ext = os.path.splitext(filename)
        ts = int(time.time() * 1000)
        dest = os.path.join(upload_dir, f"{name}_{ts}{ext}")

    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    # Path relative to workspace root so agent's read_file can find it
    rel_path = os.path.relpath(dest, settings.workspace_storage_path)

    return UploadedFileInfo(
        filename=os.path.basename(dest),
        path=rel_path,
        size=len(content),
        uploaded_at=datetime.now(timezone.utc),
    )


@router.get("/{conversation_id}")
async def list_uploads(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded files for a conversation."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "会话不存在"},
        )

    upload_dir = _get_upload_dir(conversation_id)
    if not os.path.isdir(upload_dir):
        return []

    files = []
    for fname in os.listdir(upload_dir):
        fpath = os.path.join(upload_dir, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            files.append(
                UploadedFileInfo(
                    filename=fname,
                    path=os.path.relpath(fpath, settings.workspace_storage_path),
                    size=stat.st_size,
                    uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )

    files.sort(key=lambda f: f.uploaded_at, reverse=True)
    return files


@router.delete("/{conversation_id}/{filename}")
async def delete_upload(
    conversation_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an uploaded file."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.workspace_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "会话不存在"},
        )

    upload_dir = _get_upload_dir(conversation_id)
    filepath = os.path.join(upload_dir, filename)

    # Prevent path traversal
    if os.path.realpath(filepath) != os.path.realpath(
        os.path.join(upload_dir, os.path.basename(filename))
    ):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PATH", "message": "无效的文件路径"})

    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "文件不存在"})

    os.remove(filepath)
    return {"ok": True}
