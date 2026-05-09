from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import skill_service
from app.schemas.skill import SkillResponse, SkillContentResponse

router = APIRouter(prefix="/api/v1", tags=["skills"])


# --- Public skills (MUST come before /skills/{skill_id} to avoid route conflict) ---

@router.get("/skills/public", response_model=list[SkillResponse])
async def list_public_skills(db: AsyncSession = Depends(get_db)):
    return await skill_service.get_public_skills(db)


@router.post("/skills/public/upload", response_model=SkillResponse)
async def upload_public_skill(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的 Skill 压缩包")

    zip_bytes = await file.read()
    try:
        skill = await skill_service.create_skill_from_zip(
            db=db,
            user_id=current_user.id,
            workspace_id=None,
            zip_bytes=zip_bytes,
            source="public",
        )
        return skill
    except skill_service.SkillError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# --- Private skills ---

@router.get("/skills", response_model=list[SkillResponse])
async def list_my_skills(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skills = await skill_service.get_user_skills(db, workspace_id=current_user.id)
    return skills


@router.post("/skills/upload", response_model=SkillResponse)
async def upload_skill(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的 Skill 压缩包")

    zip_bytes = await file.read()
    try:
        skill = await skill_service.create_skill_from_zip(
            db=db,
            user_id=current_user.id,
            workspace_id=current_user.id,
            zip_bytes=zip_bytes,
            source="private",
        )
        return skill
    except skill_service.SkillError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = await skill_service.get_skill_by_id(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill 不存在"})
    return skill


@router.get("/skills/{skill_id}/content", response_model=SkillContentResponse)
async def get_skill_content(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = await skill_service.get_skill_by_id(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill 不存在"})

    content = await skill_service.get_skill_content(skill.id)
    return SkillContentResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        content=content,
        source=skill.source,
    )


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill = await skill_service.get_skill_by_id(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail={"code": "SKILL_NOT_FOUND", "message": "Skill 不存在"})
    if skill.source != "private" or skill.workspace_id != current_user.id:
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "只能删除自己的私有 Skill"})

    await skill_service.delete_skill(db, skill)
    return {"ok": True}
