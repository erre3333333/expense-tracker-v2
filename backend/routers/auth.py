import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError

from database import get_db, _connect
from models.schemas import (
    UserRegister,
    UserLogin,
    UserOut,
    TokenResponse,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = "expense-tracker-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    async with _connect() as db:
        cursor = await db.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            raise credentials_exception
        return dict(row)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister):
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async with _connect() as db:
        cursor = await db.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已存在",
            )

        password_hash = pwd_context.hash(body.password)
        await db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (body.username, password_hash),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, username, created_at FROM users WHERE username = ?",
            (body.username,),
        )
        user = dict(await cursor.fetchone())
        return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin):
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async with _connect() as db:
        cursor = await db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (body.username,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        if not pwd_context.verify(body.password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        access_token = create_access_token(
            data={"sub": str(row["id"]), "username": row["username"]}
        )
        return {"access_token": access_token}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user
