import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import aiosqlite
from slugify import slugify

from lifewiki.config import settings
from lifewiki.db.repositories import source_repo
from lifewiki.models.source import Source, WikiPage, TimelineEvent, IngestLog
from lifewiki.services import wiki_compiler
from lifewiki.services.llm_service import llm_service

logger = logging.getLogger(__name__)


def _compute_file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    for chunk in open(file_path, "rb").read().split(b"\n"):
        h.update(chunk)
    return h.hexdigest()


def _detect_file_type(path: Path) -> str:
    ext = path.suffix.lower()
    type_map = {
        ".md": "markdown", ".txt": "text", ".markdown": "markdown",
        ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
        ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".ogg": "audio",
        ".mp4": "video", ".mov": "video", ".avi": "video", ".webm": "video",
        ".pdf": "pdf",
    }
    return type_map.get(ext, "unknown")


def _extract_date_from_filename(filename: str) -> str | None:
    match = re.search(r"(\d{4})(\d{2})(\d{2})", filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def _extract_title_from_markdown(content: str) -> str | None:
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _detect_category(path: Path) -> str:
    parts = path.parts
    categories = ["ai", "hot", "tennis", "dota2", "upload", "images", "audio", "video", "documents"]
    for part in parts:
        if part.lower() in categories:
            return part.lower()
    return "upload"


async def ingest_file(db: aiosqlite.Connection, file_path: Path, relative_to: Path | None = None) -> dict[str, Any]:
    if not file_path.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}

    rel_path = str(file_path.relative_to(relative_to)) if relative_to else file_path.name
    file_hash = _compute_file_hash(file_path)
    file_type = _detect_file_type(file_path)
    category = _detect_category(Path(rel_path))
    date = _extract_date_from_filename(file_path.name)
    size = file_path.stat().st_size

    existing = await source_repo.get_source_by_hash(db, file_hash)
    if existing:
        return {"status": "skipped", "reason": "duplicate", "source_id": existing.id}

    content = ""
    transcription = None
    if file_type in ("markdown", "text"):
        content = file_path.read_text(encoding="utf-8")

    title = _extract_title_from_markdown(content) if content else file_path.stem

    source = Source(
        path=rel_path,
        file_hash=file_hash,
        file_type=file_type,
        category=category,
        date=date,
        title=title,
        language="zh",
        size_bytes=size,
        transcription=transcription,
    )
    source_id = await source_repo.create_source(db, source)
    source.id = source_id

    log = IngestLog(source_id=source_id, status="processing", started_at="CURRENT_TIMESTAMP")
    log_id = await source_repo.create_ingest_log(db, log)

    try:
        analysis = await _process_source(db, source, content, transcription)
        await source_repo.update_ingest_log(db, log_id, "completed", f"Created/updated wiki pages")

        log_entry = wiki_compiler.generate_log_entry(
            "ingest", title, rel_path,
            f"Generated {len(analysis.get('topics', []))} topics, {len(analysis.get('entities', []))} entities",
        )
        await _append_to_log(log_entry)

        return {"status": "completed", "source_id": source_id, "analysis": analysis}

    except Exception as e:
        logger.exception(f"Error processing source {rel_path}")
        await source_repo.update_ingest_log(db, log_id, "failed", error_message=str(e))
        return {"status": "error", "error": str(e), "source_id": source_id}


async def ingest_directory(db: aiosqlite.Connection, dir_path: Path, pattern: str = "**/*.md") -> list[dict]:
    results = []
    base = dir_path
    for file_path in sorted(dir_path.glob(pattern)):
        if file_path.is_file():
            result = await ingest_file(db, file_path, relative_to=base)
            results.append({"file": str(file_path.relative_to(base)), **result})
    return results


async def _process_source(
    db: aiosqlite.Connection,
    source: Source,
    content: str,
    transcription: str | None = None,
) -> dict[str, Any]:
    existing_pages = await source_repo.list_wiki_pages(db)
    existing_topics = [p.title for p in existing_pages]

    analysis = await llm_service.analyze_source(
        content=content,
        category=source.category,
        date=source.date,
        file_type=source.file_type,
        existing_topics=existing_topics,
        transcription=transcription,
    )

    if isinstance(analysis, dict) and "raw_response" in analysis:
        analysis = {"summary": analysis["raw_response"][:500], "topics": [], "entities": [], "timeline_events": [], "key_insights": [], "cross_references": []}

    for topic in analysis.get("topics", []):
        await _upsert_wiki_page(db, source, topic, "topic", analysis, existing_pages)

    for entity in analysis.get("entities", []):
        await _upsert_wiki_page(db, source, entity, "entity", analysis, existing_pages)

    for evt in analysis.get("timeline_events", []):
        event = TimelineEvent(
            source_id=source.id,
            date=evt.get("date", source.date or ""),
            title=evt.get("title", ""),
            description=evt.get("description", ""),
            category=source.category,
            importance=evt.get("importance", 0.5),
        )
        await source_repo.create_timeline_event(db, event)

    await _regenerate_index(db)
    return analysis


async def _upsert_wiki_page(
    db: aiosqlite.Connection,
    source: Source,
    item: dict,
    page_type: str,
    analysis: dict[str, Any],
    existing_pages: list[WikiPage],
) -> WikiPage:
    name = item.get("name", item.get("title", "untitled"))
    slug = item.get("slug", slugify(name, lowercase=True))
    description = item.get("description", "")
    subdir = "topics" if page_type == "topic" else "entities"
    file_path = f"{subdir}/{slug}.md"

    existing = await source_repo.get_wiki_page_by_slug(db, slug)

    if existing:
        wiki_file = settings.wiki_dir / existing.file_path
        if wiki_file.exists():
            old_content = wiki_file.read_text(encoding="utf-8")
            new_content = wiki_compiler.update_wiki_page_markdown(
                old_content, analysis, source.title or source.path, source.date,
            )
        else:
            new_content = wiki_compiler.generate_wiki_page_markdown(
                name, page_type, description, analysis,
            )

        wiki_file.parent.mkdir(parents=True, exist_ok=True)
        wiki_file.write_text(new_content, encoding="utf-8")

        await source_repo.create_source_wiki_link(db, source.id, existing.id)
        existing.source_count = (existing.source_count or 0) + 1
        page = WikiPage(
            id=existing.id, slug=slug, title=name, page_type=page_type,
            file_path=file_path, summary=description, source_count=existing.source_count,
        )
        await source_repo.create_wiki_page(db, page)
        await source_repo.update_wiki_page_compiled(db, existing.id)
        return existing
    else:
        content = wiki_compiler.generate_wiki_page_markdown(name, page_type, description, analysis)
        wiki_file = settings.wiki_dir / file_path
        wiki_file.parent.mkdir(parents=True, exist_ok=True)
        wiki_file.write_text(content, encoding="utf-8")

        page = WikiPage(
            slug=slug, title=name, page_type=page_type,
            file_path=file_path, summary=description, source_count=1,
        )
        page_id = await source_repo.create_wiki_page(db, page)
        page.id = page_id

        await source_repo.create_source_wiki_link(db, source.id, page_id)

        cross_refs = await llm_service.generate_cross_references(
            name, description, [vars(p) for p in existing_pages if p.id != page_id],
        )
        for ref in cross_refs:
            target_slug = ref.get("slug", ref.get("target_slug", ""))
            target = await source_repo.get_wiki_page_by_slug(db, target_slug)
            if target:
                await source_repo.create_cross_ref(
                    db, page_id, target.id,
                    ref.get("relation_type", "related"),
                    ref.get("context", ""),
                )

        await source_repo.update_wiki_page_compiled(db, page_id)
        return page


async def _regenerate_index(db: aiosqlite.Connection) -> None:
    pages = await source_repo.list_wiki_pages(db)
    index_content = wiki_compiler.generate_index_markdown(pages)
    index_path = settings.wiki_dir / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(index_content, encoding="utf-8")


async def _append_to_log(entry: str) -> None:
    log_path = settings.wiki_dir / "log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# LifeWiki 操作日志\n", encoding="utf-8")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
