from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Source:
    id: int | None = None
    path: str = ""
    file_hash: str = ""
    file_type: str = "markdown"
    category: str = "upload"
    date: str | None = None
    title: str | None = None
    summary: str | None = None
    language: str = "zh"
    size_bytes: int | None = None
    media_metadata: str | None = None
    transcription: str | None = None
    ingested_at: str | None = None
    created_at: str | None = None


@dataclass
class WikiPage:
    id: int | None = None
    slug: str = ""
    title: str = ""
    page_type: str = "topic"
    file_path: str = ""
    summary: str | None = None
    source_count: int = 0
    last_compiled_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class TimelineEvent:
    id: int | None = None
    source_id: int | None = None
    date: str = ""
    title: str = ""
    description: str | None = None
    category: str | None = None
    wiki_page_id: int | None = None
    importance: float = 0.5
    created_at: str | None = None


@dataclass
class IngestLog:
    id: int | None = None
    source_id: int | None = None
    operation: str = "ingest"
    status: str = "pending"
    result_summary: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    created_at: str | None = None
