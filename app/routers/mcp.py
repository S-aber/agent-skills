"""MCP server management API — zip upload, repository, enable/disable toggle."""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.mcp_server import MCPServer
from app.schemas.mcp import MCPServerResponse, MCPServerToggleResponse
from app.services.auth_service import get_current_user
from app.services.mcp_manager import mcp_manager, MCPError

logger = logging.getLogger("mcp_router")
router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


def _to_response(s: MCPServer) -> dict:
    return {
        "id": s.id,
        "workspace_id": s.workspace_id,
        "uploader_id": s.uploader_id,
        "source": s.source,
        "name": s.name,
        "description": s.description,
        "command": s.command,
        "args": s.args_list,
        "enabled": s.enabled,
        "created_at": s.created_at,
    }


# ---- Public servers (before /servers/{id} to avoid route conflict) ----

@router.get("/servers/public", response_model=list[MCPServerResponse])
async def list_public_servers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.source == "public")
        .order_by(MCPServer.created_at.desc())
    )
    servers = result.scalars().all()
    return [_to_response(s) for s in servers]


@router.post("/servers/public/upload", response_model=MCPServerResponse)
async def upload_public_server(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的 MCP 压缩包")

    zip_bytes = await file.read()
    try:
        server = await mcp_manager.create_mcp_from_zip(
            db=db,
            user_id=current_user.id,
            workspace_id=None,
            zip_bytes=zip_bytes,
            source="public",
        )
        return _to_response(server)
    except MCPError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# ---- Private servers ----

@router.get("/servers", response_model=list[MCPServerResponse])
async def list_my_servers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MCPServer)
        .where(MCPServer.workspace_id == current_user.id, MCPServer.source == "private")
        .order_by(MCPServer.created_at.desc())
    )
    servers = result.scalars().all()
    return [_to_response(s) for s in servers]


@router.post("/servers/upload", response_model=MCPServerResponse)
async def upload_server(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的 MCP 压缩包")

    zip_bytes = await file.read()
    try:
        server = await mcp_manager.create_mcp_from_zip(
            db=db,
            user_id=current_user.id,
            workspace_id=current_user.id,
            zip_bytes=zip_bytes,
            source="private",
        )
        return _to_response(server)
    except MCPError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.get("/servers/{server_id}", response_model=MCPServerResponse)
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")
    if server.source == "private" and server.workspace_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return _to_response(server)


@router.delete("/servers/{server_id}")
async def delete_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.workspace_id == current_user.id,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")

    await mcp_manager.delete_server(db, server)
    return {"ok": True}


@router.patch("/servers/{server_id}/toggle", response_model=MCPServerToggleResponse)
async def toggle_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == server_id,
            MCPServer.workspace_id == current_user.id,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP 服务器不存在")

    server.enabled = not server.enabled
    await db.commit()
    await db.refresh(server)

    # If disabled, disconnect active session
    if not server.enabled:
        await mcp_manager.disconnect(server.name)

    return MCPServerToggleResponse(id=server.id, name=server.name, enabled=server.enabled)
