import uuid
from typing import Annotated

from fastapi import Depends
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Firm, User
from db.session import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user is None:
        firm = Firm(id=uuid.uuid4(), name="Default Firm")
        db.add(firm)
        await db.flush()
        user = User(
            id=uuid.uuid4(),
            email="admin@lexmind.local",
            hashed_password=hash_password("lexmind"),
            firm_id=firm.id,
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
