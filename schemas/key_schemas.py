from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_serializer


# ---------- FakeKey ----------

class FakeKeyCreate(BaseModel):
    name: str = ""
    enabled: bool = True


class FakeKeyUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None


class FakeKeyOut(BaseModel):
    id: int
    key: str
    name: str
    enabled: bool
    created_at: datetime

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime('%Y-%m-%dT%H:%M:%S')

    class Config:
        from_attributes = True


# ---------- RealKey ----------

class RealKeyCreate(BaseModel):
    provider: str  # 接口规范：openai / anthropic
    base_url: str
    key: str
    name: str = ""
    enabled: bool = True


class RealKeyUpdate(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    key: Optional[str] = None
    name: Optional[str] = None
    enabled: Optional[bool] = None


class RealKeyOut(BaseModel):
    id: int
    provider: str
    base_url: str
    name: str
    enabled: bool
    created_at: datetime
    # 真密钥本身不返回

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime('%Y-%m-%dT%H:%M:%S')

    class Config:
        from_attributes = True


# ---------- Mapping ----------

class MappingCreate(BaseModel):
    fake_key_id: int
    real_key_id: int
    priority: int = 0


class MappingOut(BaseModel):
    id: int
    fake_key_id: int
    real_key_id: int
    priority: int
    fake_key: Optional[FakeKeyOut] = None
    real_key: Optional[RealKeyOut] = None

    class Config:
        from_attributes = True
