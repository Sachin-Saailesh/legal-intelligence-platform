import uuid
from typing import Annotated

import bcrypt
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Firm, User
from db.session import get_db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


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
