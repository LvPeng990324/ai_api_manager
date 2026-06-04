from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, field_serializer


class RequestLogOut(BaseModel):
    id: int
    fake_key_id: int
    real_key_id: Optional[int]
    provider: str
    model: str
    endpoint: str
    status_code: int
    latency_ms: int
    tokens_input: int
    tokens_output: int
    request_preview: str
    created_at: datetime

    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.strftime('%Y-%m-%dT%H:%M:%S')

    class Config:
        from_attributes = True


class DailyStatsOut(BaseModel):
    id: int
    fake_key_id: int
    date: date
    request_count: int
    tokens_input: int
    tokens_output: int

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    today_requests: int
    today_tokens_input: int
    today_tokens_output: int
    total_requests_7d: int
    total_tokens_input_7d: int
    total_tokens_output_7d: int
    top_keys: List[dict]
