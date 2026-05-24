import aiosqlite
from typing import Sequence

from lifewiki.models.source import Source, WikiPage, TimelineEvent, IngestLog


def _row_to_source(row: aiosqlite.Row) -> Source:
    return Source(**{k: row[k] for k in row.keys()})


def _row_to_page(row: aiosqlite.Row) -> WikiPage:
    return WikiPage(**{k: row[k] for k in row.keys()})


async def create_source(db: aiosqlite.Connection, source: Source) -> int:
    cursor = await db.execute(
        """INSERT INTO sources (path, file_hash, file_type, category, date, title, summary,
           language, size_bytes, media_metadata, transcription)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (source.path, source.file_hash, source.file_type, source.category, source.date,
         source.title, source.summary, source.language, source.size_bytes,
         source.media_metadata, source.transcription),
    )
    await db.commit()
    return cursor.lastrowid


async def get_source_by_path(db: aiosqlite.Connection, path: str) -> Source | None:
    cursor = await db.execute("SELECT * FROM sources WHERE path = ?", (path,))
    row = await cursor.fetchone()
    return _row_to_source(row) if row else None


async def get_source_by_hash(db: aiosqlite.Connection, file_hash: str) -> Source | None:
    cursor = await db.execute("SELECT * FROM sources WHERE file_hash = ?", (file_hash,))
    row = await cursor.fetchone()
    return _row_to_source(row) if row else None


async def list_sources(db: aiosqlite.Connection, limit: int = 50, offset: int = 0) -> list[Source]:
    cursor = await db.execute(
        "SELECT * FROM sources ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    return [_row_to_source(r) for r in rows]


async def create_wiki_page(db: aiosqlite.Connection, page: WikiPage) -> int:
    cursor = await db.execute(
        """INSERT INTO wiki_pages (slug, title, page_type, file_path, summary, source_count)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(slug) DO UPDATE SET
             title=excluded.title, summary=excluded.summary,
             source_count=excluded.source_count,
             updated_at=CURRENT_TIMESTAMP""",
        (page.slug, page.title, page.page_type, page.file_path, page.summary, page.source_count),
    )
    await db.commit()
    return cursor.lastrowid


async def get_wiki_page_by_slug(db: aiosqlite.Connection, slug: str) -> WikiPage | None:
    cursor = await db.execute("SELECT * FROM wiki_pages WHERE slug = ?", (slug,))
    row = await cursor.fetchone()
    return _row_to_page(row) if row else None


async def list_wiki_pages(db: aiosqlite.Connection, page_type: str | None = None) -> list[WikiPage]:
    if page_type:
        cursor = await db.execute(
            "SELECT * FROM wiki_pages WHERE page_type = ? ORDER BY updated_at DESC",
            (page_type,),
        )
    else:
        cursor = await db.execute("SELECT * FROM wiki_pages ORDER BY updated_at DESC")
    rows = await cursor.fetchall()
    return [_row_to_page(r) for r in rows]


async def update_wiki_page_compiled(db: aiosqlite.Connection, page_id: int) -> None:
    await db.execute(
        "UPDATE wiki_pages SET last_compiled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (page_id,),
    )
    await db.commit()


async def create_source_wiki_link(db: aiosqlite.Connection, source_id: int, wiki_page_id: int, relevance: str | None = None) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO source_wiki_links (source_id, wiki_page_id, relevance) VALUES (?, ?, ?)",
        (source_id, wiki_page_id, relevance),
    )
    await db.commit()


async def create_cross_ref(db: aiosqlite.Connection, from_id: int, to_id: int, relation_type: str, context: str | None = None) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO wiki_cross_refs (from_page_id, to_page_id, relation_type, context) VALUES (?, ?, ?, ?)",
        (from_id, to_id, relation_type, context),
    )
    await db.commit()


async def create_timeline_event(db: aiosqlite.Connection, event: TimelineEvent) -> int:
    cursor = await db.execute(
        """INSERT INTO timeline_events (source_id, date, title, description, category, wiki_page_id, importance)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (event.source_id, event.date, event.title, event.description, event.category, event.wiki_page_id, event.importance),
    )
    await db.commit()
    return cursor.lastrowid


async def list_timeline_events(
    db: aiosqlite.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> list[TimelineEvent]:
    query = "SELECT * FROM timeline_events WHERE 1=1"
    params: list = []
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY date DESC, importance DESC LIMIT ?"
    params.append(limit)
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [TimelineEvent(**{k: r[k] for k in r.keys()}) for r in rows]


async def create_ingest_log(db: aiosqlite.Connection, log: IngestLog) -> int:
    cursor = await db.execute(
        """INSERT INTO ingest_log (source_id, operation, status, result_summary, error_message, started_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (log.source_id, log.operation, log.status, log.result_summary, log.error_message, log.started_at),
    )
    await db.commit()
    return cursor.lastrowid


async def update_ingest_log(db: aiosqlite.Connection, log_id: int, status: str, result_summary: str | None = None, error_message: str | None = None) -> None:
    await db.execute(
        """UPDATE ingest_log SET status=?, result_summary=?, error_message=?, completed_at=CURRENT_TIMESTAMP WHERE id=?""",
        (status, result_summary, error_message, log_id),
    )
    await db.commit()


async def search_wiki_pages(db: aiosqlite.Connection, query: str, limit: int = 20) -> list[dict]:
    cursor = await db.execute(
        """SELECT wp.id, wp.slug, wp.title, wp.page_type, wp.summary, snippet(wiki_pages_fts, 2, '<mark>', '</mark>', '...', 30) as snippet
           FROM wiki_pages_fts fts
           JOIN wiki_pages wp ON wp.id = fts.rowid
           WHERE wiki_pages_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (query, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_stats(db: aiosqlite.Connection) -> dict:
    stats = {}
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM sources")
    stats["source_count"] = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM wiki_pages")
    stats["page_count"] = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM timeline_events")
    stats["event_count"] = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT COUNT(*) as cnt FROM wiki_cross_refs")
    stats["cross_ref_count"] = (await cursor.fetchone())["cnt"]
    cursor = await db.execute("SELECT MIN(date) as earliest, MAX(date) as latest FROM timeline_events")
    row = await cursor.fetchone()
    stats["earliest_date"] = row["earliest"]
    stats["latest_date"] = row["latest"]
    return stats


async def get_recent_ingests(db: aiosqlite.Connection, limit: int = 10) -> list[dict]:
    cursor = await db.execute(
        """SELECT il.*, s.title as source_title, s.file_type, s.category
           FROM ingest_log il
           LEFT JOIN sources s ON s.id = il.source_id
           ORDER BY il.created_at DESC LIMIT ?""",
        (limit,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_page_cross_refs(db: aiosqlite.Connection, page_id: int) -> list[dict]:
    cursor = await db.execute(
        """SELECT wp.slug, wp.title, wp.page_type, cr.relation_type, cr.context
           FROM wiki_cross_refs cr
           JOIN wiki_pages wp ON wp.id = cr.to_page_id
           WHERE cr.from_page_id = ?""",
        (page_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]


async def get_page_sources(db: aiosqlite.Connection, page_id: int) -> list[dict]:
    cursor = await db.execute(
        """SELECT s.id, s.path, s.title, s.date, s.file_type, s.category, swl.relevance
           FROM source_wiki_links swl
           JOIN sources s ON s.id = swl.source_id
           WHERE swl.wiki_page_id = ?
           ORDER BY s.date DESC""",
        (page_id,),
    )
    return [dict(r) for r in await cursor.fetchall()]
