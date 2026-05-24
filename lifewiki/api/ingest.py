import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Form

from lifewiki.config import settings
from lifewiki.db.database import get_db
from lifewiki.services.ingest_service import ingest_file, ingest_directory

router = APIRouter()


@router.post("/file")
async def ingest_uploaded_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form("upload"),
):
    upload_dir = settings.sources_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    db = await get_db()
    try:
        result = await ingest_file(db, dest, relative_to=settings.sources_dir)
        return result
    finally:
        await db.close()


@router.post("/directory")
async def ingest_from_directory(
    background_tasks: BackgroundTasks,
    path: str = "",
    pattern: str = "**/*.md",
):
    dir_path = Path(path) if path else settings.sources_dir
    if not dir_path.exists():
        return {"status": "error", "error": f"Directory not found: {dir_path}"}

    db = await get_db()
    try:
        results = await ingest_directory(db, dir_path, pattern)
        return {"status": "completed", "results": results}
    finally:
        await db.close()


@router.get("/status")
async def get_ingest_status(limit: int = 20):
    from lifewiki.db.repositories import source_repo
    db = await get_db()
    try:
        recent = await source_repo.get_recent_ingests(db, limit)
        return {"ingests": recent}
    finally:
        await db.close()
