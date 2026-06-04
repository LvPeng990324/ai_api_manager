from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import DailyStats, FakeKey, RequestLog
from schemas.stats_schemas import DashboardStats


async def record_request(
    db: AsyncSession,
    fake_key_id: int,
    real_key_id: Optional[int],
    provider: str,
    model: str,
    endpoint: str,
    status_code: int,
    latency_ms: int,
    tokens_input: int,
    tokens_output: int,
    request_preview: str,
) -> None:
    log = RequestLog(
        fake_key_id=fake_key_id,
        real_key_id=real_key_id,
        provider=provider,
        model=model,
        endpoint=endpoint,
        status_code=status_code,
        latency_ms=latency_ms,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        request_preview=request_preview,
    )
    db.add(log)

    # 更新或创建每日统计
    today = date.today()
    result = await db.execute(
        select(DailyStats).where(
            DailyStats.fake_key_id == fake_key_id,
            DailyStats.date == today,
        )
    )
    stats = result.scalar_one_or_none()
    if stats:
        stats.request_count += 1
        stats.tokens_input += tokens_input
        stats.tokens_output += tokens_output
    else:
        stats = DailyStats(
            fake_key_id=fake_key_id,
            date=today,
            request_count=1,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )
        db.add(stats)

    await db.commit()


async def get_logs(
    db: AsyncSession,
    fake_key_id: Optional[int] = None,
    provider: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[RequestLog], int]:
    query = select(RequestLog)
    count_query = select(func.count(RequestLog.id))

    if fake_key_id:
        query = query.where(RequestLog.fake_key_id == fake_key_id)
        count_query = count_query.where(RequestLog.fake_key_id == fake_key_id)
    if provider:
        query = query.where(RequestLog.provider == provider)
        count_query = count_query.where(RequestLog.provider == provider)
    if start_date:
        query = query.where(func.date(RequestLog.created_at) >= start_date)
        count_query = count_query.where(func.date(RequestLog.created_at) >= start_date)
    if end_date:
        query = query.where(func.date(RequestLog.created_at) <= end_date)
        count_query = count_query.where(func.date(RequestLog.created_at) <= end_date)

    query = query.order_by(RequestLog.id.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    total_result = await db.execute(count_query)
    return result.scalars().all(), total_result.scalar_one()


async def get_dashboard_stats(db: AsyncSession) -> DashboardStats:
    today = date.today()
    seven_days_ago = today - timedelta(days=6)

    # 今日统计
    today_result = await db.execute(
        select(
            func.coalesce(func.sum(DailyStats.request_count), 0),
            func.coalesce(func.sum(DailyStats.tokens_input), 0),
            func.coalesce(func.sum(DailyStats.tokens_output), 0),
        ).where(DailyStats.date == today)
    )
    today_requests, today_input, today_output = today_result.one()

    # 近7日统计
    week_result = await db.execute(
        select(
            func.coalesce(func.sum(DailyStats.request_count), 0),
            func.coalesce(func.sum(DailyStats.tokens_input), 0),
            func.coalesce(func.sum(DailyStats.tokens_output), 0),
        ).where(DailyStats.date >= seven_days_ago)
    )
    week_requests, week_input, week_output = week_result.one()

    # Top keys (近7日按请求量)
    top_result = await db.execute(
        select(
            DailyStats.fake_key_id,
            FakeKey.name,
            FakeKey.key,
            func.sum(DailyStats.request_count).label("total"),
        )
        .join(FakeKey, DailyStats.fake_key_id == FakeKey.id)
        .where(DailyStats.date >= seven_days_ago)
        .group_by(DailyStats.fake_key_id)
        .order_by(func.sum(DailyStats.request_count).desc())
        .limit(10)
    )
    top_keys = [
        {
            "fake_key_id": row.fake_key_id,
            "name": row.name,
            "key": row.key,
            "total_requests": row.total,
        }
        for row in top_result.all()
    ]

    return DashboardStats(
        today_requests=int(today_requests),
        today_tokens_input=int(today_input),
        today_tokens_output=int(today_output),
        total_requests_7d=int(week_requests),
        total_tokens_input_7d=int(week_input),
        total_tokens_output_7d=int(week_output),
        top_keys=top_keys,
    )


async def get_stats_by_key(
    db: AsyncSession,
    fake_key_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[dict]:
    query = (
        select(
            DailyStats.fake_key_id,
            FakeKey.name,
            FakeKey.key,
            DailyStats.date,
            DailyStats.request_count,
            DailyStats.tokens_input,
            DailyStats.tokens_output,
        )
        .join(FakeKey, DailyStats.fake_key_id == FakeKey.id)
    )

    if fake_key_id:
        query = query.where(DailyStats.fake_key_id == fake_key_id)
    if start_date:
        query = query.where(DailyStats.date >= start_date)
    if end_date:
        query = query.where(DailyStats.date <= end_date)

    query = query.order_by(DailyStats.date.desc(), DailyStats.fake_key_id.desc())

    result = await db.execute(query)
    rows = result.all()
    return [
        {
            "fake_key_id": row.fake_key_id,
            "fake_key_name": row.name,
            "fake_key": row.key,
            "date": row.date.isoformat(),
            "request_count": row.request_count,
            "tokens_input": row.tokens_input,
            "tokens_output": row.tokens_output,
        }
        for row in rows
    ]
