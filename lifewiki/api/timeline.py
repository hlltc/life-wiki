from fastapi import APIRouter, Query

from lifewiki.db.database import get_db
from lifewiki.db.repositories import source_repo

router = APIRouter()


@router.get("")
async def get_timeline(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    limit: int = 100,
):
    db = await get_db()
    try:
        events = await source_repo.list_timeline_events(db, start_date, end_date, category, limit)
        return {"events": [
            {"id": e.id, "date": e.date, "title": e.title, "description": e.description,
             "category": e.category, "importance": e.importance}
            for e in events
        ]}
    finally:
        await db.close()
