from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
