from fastapi import APIRouter
from pathlib import Path

from lifewiki.config import settings
from lifewiki.db.database import get_db
from lifewiki.db.repositories import source_repo

router = APIRouter()


@router.get("")
async def list_pages(page_type: str | None = None, limit: int = 50):
    db = await get_db()
    try:
        pages = await source_repo.list_wiki_pages(db, page_type)
        return {"pages": [
            {"id": p.id, "slug": p.slug, "title": p.title, "page_type": p.page_type,
             "summary": p.summary, "source_count": p.source_count, "updated_at": p.updated_at}
            for p in pages[:limit]
        ]}
    finally:
        await db.close()


@router.get("/index")
async def get_index():
    index_path = settings.wiki_dir / "index.md"
    if index_path.exists():
        return {"content": index_path.read_text(encoding="utf-8")}
    return {"content": "# Index not yet generated"}


@router.get("/log")
async def get_log():
    log_path = settings.wiki_dir / "log.md"
    if log_path.exists():
        return {"content": log_path.read_text(encoding="utf-8")}
    return {"content": "# Log not yet generated"}


@router.get("/{slug}")
async def get_page(slug: str):
    db = await get_db()
    try:
        page = await source_repo.get_wiki_page_by_slug(db, slug)
        if not page:
            return {"error": "Page not found"}, 404

        wiki_file = settings.wiki_dir / page.file_path
        content = wiki_file.read_text(encoding="utf-8") if wiki_file.exists() else ""
        sources = await source_repo.get_page_sources(db, page.id)
        refs = await source_repo.get_page_cross_refs(db, page.id)

        return {
            "page": {
                "id": page.id, "slug": page.slug, "title": page.title,
                "page_type": page.page_type, "summary": page.summary,
                "source_count": page.source_count, "last_compiled_at": page.last_compiled_at,
            },
            "content": content,
            "sources": sources,
            "cross_references": refs,
        }
    finally:
        await db.close()
