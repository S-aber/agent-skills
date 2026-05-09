from typing import Annotated
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.database import get_db
from app.utils.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from jose import JWTError


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


async def register_user(db: AsyncSession, username: str, password: str) -> User:
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise AuthError("USER_EXISTS", "用户名已存在", 409)

    user = User(
        username=username,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, username: str, password: str) -> dict:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise AuthError("AUTH_FAILED", "用户名或密码错误", 401)

    return {
        "access_token": create_access_token(user.id, user.username),
        "refresh_token": create_refresh_token(user.id, user.username),
        "token_type": "bearer",
    }


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("AUTH_FAILED", "缺少认证令牌", 401)

    token = authorization[7:]  # Remove "Bearer " prefix
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise AuthError("AUTH_FAILED", "无效的令牌", 401)
    except JWTError:
        raise AuthError("AUTH_FAILED", "无效的令牌", 401)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthError("AUTH_FAILED", "用户不存在", 401)
    return user
