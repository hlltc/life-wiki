from fastapi import APIRouter, Query

from lifewiki.db.database import get_db
from lifewiki.db.repositories import source_repo
from lifewiki.services.llm_service import llm_service

router = APIRouter()


@router.get("/search")
async def search(q: str = Query(..., min_length=1), limit: int = 20):
    db = await get_db()
    try:
        results = await source_repo.search_wiki_pages(db, q, limit)
        return {"query": q, "results": results}
    finally:
        await db.close()


@router.post("/ask")
async def ask_question(question: str):
    db = await get_db()
    try:
        results = await source_repo.search_wiki_pages(db, question, limit=5)
        if not results:
            return {"answer": "Wiki 中暂无相关内容。请先导入更多资料。", "sources": []}

        wiki_context = "\n\n".join(
            f"## {r['title']} ({r['page_type']})\n{r.get('summary', r.get('snippet', ''))}"
            for r in results
        )

        answer = await llm_service.answer_question(question, wiki_context)
        return {"answer": answer, "sources": results}
    finally:
        await db.close()
