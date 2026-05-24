import aiosqlite
from pathlib import Path

from lifewiki.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,
    file_type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'upload',
    date TEXT,
    title TEXT,
    summary TEXT,
    language TEXT DEFAULT 'zh',
    size_bytes INTEGER,
    media_metadata TEXT,
    transcription TEXT,
    ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wiki_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    page_type TEXT NOT NULL DEFAULT 'topic',
    file_path TEXT NOT NULL,
    summary TEXT,
    source_count INTEGER DEFAULT 0,
    last_compiled_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_wiki_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    wiki_page_id INTEGER NOT NULL REFERENCES wiki_pages(id),
    relevance TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, wiki_page_id)
);

CREATE TABLE IF NOT EXISTS wiki_cross_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_page_id INTEGER NOT NULL REFERENCES wiki_pages(id),
    to_page_id INTEGER NOT NULL REFERENCES wiki_pages(id),
    relation_type TEXT,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_page_id, to_page_id)
);

CREATE TABLE IF NOT EXISTS timeline_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id),
    date TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    wiki_page_id INTEGER REFERENCES wiki_pages(id),
    importance REAL DEFAULT 0.5,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES sources(id),
    operation TEXT NOT NULL DEFAULT 'ingest',
    status TEXT NOT NULL DEFAULT 'pending',
    result_summary TEXT,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sources_category ON sources(category);
CREATE INDEX IF NOT EXISTS idx_sources_date ON sources(date);
CREATE INDEX IF NOT EXISTS idx_wiki_pages_type ON wiki_pages(page_type);
CREATE INDEX IF NOT EXISTS idx_timeline_date ON timeline_events(date);
CREATE INDEX IF NOT EXISTS idx_ingest_status ON ingest_log(status);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS wiki_pages_fts USING fts5(
    title,
    summary,
    content,
    content='wiki_pages',
    content_rowid='id',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS wiki_pages_ai AFTER INSERT ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(rowid, title, summary, content)
    VALUES (new.id, new.title, new.summary, '');
END;

CREATE TRIGGER IF NOT EXISTS wiki_pages_ad AFTER DELETE ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(wiki_pages_fts, rowid, title, summary, content)
    VALUES ('delete', old.id, old.title, old.summary, '');
END;

CREATE TRIGGER IF NOT EXISTS wiki_pages_au AFTER UPDATE ON wiki_pages BEGIN
    INSERT INTO wiki_pages_fts(wiki_pages_fts, rowid, title, summary, content)
    VALUES ('delete', old.id, old.title, old.summary, '');
    INSERT INTO wiki_pages_fts(rowid, title, summary, content)
    VALUES (new.id, new.title, new.summary, '');
END;
"""


async def init_db() -> None:
    db_path = settings.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(SCHEMA_SQL)
        await db.executescript(FTS_SQL)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(settings.db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db
