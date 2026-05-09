import os
import re
import io
import uuid
import shutil
import zipfile
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.skill import Skill
from app.config import get_settings
import yaml

settings = get_settings()


class SkillError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


def _find_skill_md(folder: str) -> str:
    """Recursively search for SKILL.md in extracted folder (case-insensitive)."""
    for root, dirs, files in os.walk(folder):
        for f in files:
            if f.lower() == "skill.md":
                return os.path.join(root, f)
    raise SkillError("SKILL_PARSE_ERROR", "ZIP 中未找到 SKILL.md 文件")


def _parse_skill_md(filepath: str) -> tuple[str, str]:
    """Parse SKILL.md, returns (name, description) from YAML frontmatter."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        raise SkillError("SKILL_PARSE_ERROR", "SKILL.md 缺少 YAML 头 (--- ... ---)")

    try:
        yaml_data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        raise SkillError("SKILL_PARSE_ERROR", f"SKILL.md YAML 解析失败: {str(e)}")

    if not yaml_data or not isinstance(yaml_data, dict):
        raise SkillError("SKILL_PARSE_ERROR", "SKILL.md YAML 头为空")

    name = yaml_data.get("name", "").strip()
    description = yaml_data.get("description", "").strip()

    if not name:
        raise SkillError("SKILL_PARSE_ERROR", "SKILL.md 缺少必填字段: name")
    if not description:
        raise SkillError("SKILL_PARSE_ERROR", "SKILL.md 缺少必填字段: description")

    return name, description


async def create_skill_from_zip(
    db: AsyncSession,
    user_id: str,
    workspace_id: str | None,
    zip_bytes: bytes,
    source: str = "private",
) -> Skill:
    """Extract a skill zip, find SKILL.md, store as a folder."""

    # Extract zip to temp dir first to find SKILL.md
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Security: prevent zip slip
            for member in zf.infolist():
                target = os.path.realpath(os.path.join(tmpdir, member.filename))
                if not target.startswith(os.path.realpath(tmpdir) + os.sep):
                    raise SkillError("SKILL_PARSE_ERROR", "ZIP 包含非法路径")

            zf.extractall(tmpdir)

        # Find SKILL.md — recursive search handles any nesting
        skill_md_path = _find_skill_md(tmpdir)
        name, description = _parse_skill_md(skill_md_path)

        # Move to permanent storage
        skill_id = str(uuid.uuid4())
        skill_folder = os.path.join(settings.skills_storage_path, skill_id)
        os.makedirs(skill_folder, exist_ok=True)

        # Copy all extracted files
        entries = os.listdir(tmpdir)
        for entry in entries:
            src = os.path.join(tmpdir, entry)
            dst = os.path.join(skill_folder, entry)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    # Verify SKILL.md exists in final location
    final_md = _find_skill_md(skill_folder)

    skill = Skill(
        id=skill_id,
        workspace_id=workspace_id if source == "private" else None,
        uploader_id=user_id,
        source=source,
        name=name,
        description=description,
        folder_path=skill_folder,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


async def get_user_skills(
    db: AsyncSession, workspace_id: str | None
) -> list[Skill]:
    result = await db.execute(
        select(Skill)
        .where(Skill.workspace_id == workspace_id, Skill.source == "private")
        .order_by(Skill.created_at.desc())
    )
    return list(result.scalars().all())


async def get_public_skills(db: AsyncSession) -> list[Skill]:
    result = await db.execute(
        select(Skill)
        .where(Skill.source == "public")
        .order_by(Skill.created_at.desc())
    )
    return list(result.scalars().all())


async def get_skill_by_id(db: AsyncSession, skill_id: str) -> Skill | None:
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalar_one_or_none()


async def get_skill_content(skill_id: str) -> str:
    skill_folder = os.path.join(settings.skills_storage_path, skill_id)
    if not os.path.exists(skill_folder):
        raise SkillError("SKILL_NOT_FOUND", f"Skill 不存在: {skill_id}", 404)
    skill_md_path = _find_skill_md(skill_folder)
    with open(skill_md_path, "r", encoding="utf-8") as f:
        return f.read()


async def delete_skill(db: AsyncSession, skill: Skill):
    # Remove files
    if os.path.exists(skill.folder_path):
        shutil.rmtree(skill.folder_path)
    await db.delete(skill)
    await db.commit()
