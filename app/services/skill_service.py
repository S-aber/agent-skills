import os
import re
import uuid
import shutil
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


def parse_skill_md(content: str) -> tuple[str, str]:
    """Parse SKILL.md, returns (name, description) from YAML frontmatter."""
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


async def create_skill(
    db: AsyncSession,
    user_id: str,
    workspace_id: str,
    filename: str,
    content: bytes,
    source: str = "private",
) -> Skill:
    name, description = parse_skill_md(content.decode("utf-8"))

    skill_id = str(uuid.uuid4())
    skill_folder = os.path.join(settings.skills_storage_path, skill_id)
    os.makedirs(skill_folder, exist_ok=True)

    # Write SKILL.md
    skill_md_path = os.path.join(skill_folder, "SKILL.md")
    with open(skill_md_path, "wb") as f:
        f.write(content)

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
    skill_md_path = os.path.join(skill_folder, "SKILL.md")
    if not os.path.exists(skill_md_path):
        raise SkillError("SKILL_NOT_FOUND", f"Skill 文件不存在: {skill_id}", 404)
    with open(skill_md_path, "r", encoding="utf-8") as f:
        return f.read()


async def delete_skill(db: AsyncSession, skill: Skill):
    # Remove files
    if os.path.exists(skill.folder_path):
        shutil.rmtree(skill.folder_path)
    await db.delete(skill)
    await db.commit()
