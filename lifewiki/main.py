import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lifewiki.config import settings
from lifewiki.db.database import init_db, get_db
from lifewiki.api import ingest, wiki, query, timeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.sources_dir.mkdir(parents=True, exist_ok=True)
    settings.wiki_dir.mkdir(parents=True, exist_ok=True)
    settings.topics_dir.mkdir(parents=True, exist_ok=True)
    settings.entities_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    logger.info("LifeWiki started. Database initialized.")
    yield


app = FastAPI(title="LifeWiki", description="Personal Life Wiki powered by LLM", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/data", StaticFiles(directory=str(settings.data_dir)), name="data")

app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(wiki.router, prefix="/api/wiki", tags=["wiki"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(timeline.router, prefix="/api/timeline", tags=["timeline"])


@app.get("/")
async def home(request: Request):
    db = await get_db()
    try:
        stats = await _get_dashboard_data(db)
        return templates.TemplateResponse("index.html", {"request": request, **stats})
    finally:
        await db.close()


@app.get("/wiki/{slug}")
async def view_wiki_page(request: Request, slug: str):
    db = await get_db()
    try:
        from lifewiki.db.repositories import source_repo
        page = await source_repo.get_wiki_page_by_slug(db, slug)
        if not page:
            return templates.TemplateResponse("404.html", {"request": request, "message": f"Wiki page '{slug}' not found"}, status_code=404)

        wiki_file = settings.wiki_dir / page.file_path
        content = wiki_file.read_text(encoding="utf-8") if wiki_file.exists() else "Content not found."

        sources = await source_repo.get_page_sources(db, page.id)
        refs = await source_repo.get_page_cross_refs(db, page.id)

        import markdown as md
        html_content = md.markdown(content, extensions=["extra", "wikilinks", "toc"])

        return templates.TemplateResponse("wiki_page.html", {
            "request": request,
            "page": page,
            "content": html_content,
            "sources": sources,
            "refs": refs,
        })
    finally:
        await db.close()


@app.get("/timeline")
async def view_timeline(request: Request):
    return templates.TemplateResponse("timeline.html", {"request": request})


@app.get("/search")
async def view_search(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})


@app.get("/ingest")
async def view_ingest(request: Request):
    return templates.TemplateResponse("ingest.html", {"request": request})


async def _get_dashboard_data(db):
    from lifewiki.db.repositories import source_repo
    stats = await source_repo.get_stats(db)
    recent = await source_repo.get_recent_ingests(db)
    pages = await source_repo.list_wiki_pages(db, limit=10)
    return {"stats": stats, "recent_ingests": recent, "recent_pages": pages}
