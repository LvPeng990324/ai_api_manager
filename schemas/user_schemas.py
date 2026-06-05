from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime('%Y-%m-%dT%H:%M:%S')

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
