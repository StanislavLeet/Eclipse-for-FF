from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import TokenResponse, UserRegister, UserLogin, UserResponse
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_email,
    get_user_by_username,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    if await get_user_by_email(db, body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if await get_user_by_username(db, body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
    user = await create_user(db, email=body.email, username=body.username, password=body.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    # JWT is stateless; client discards the token. Nothing to do server-side.
    return None
