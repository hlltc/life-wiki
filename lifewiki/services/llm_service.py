import json
import logging
from typing import Any

import anthropic

from lifewiki.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.claude_max_tokens
        self.temperature = settings.claude_temperature

    async def analyze_source(
        self,
        content: str,
        category: str = "upload",
        date: str | None = None,
        file_type: str = "markdown",
        existing_topics: list[str] | None = None,
        transcription: str | None = None,
    ) -> dict[str, Any]:
        prompt = self._load_prompt("ingest_source")
        topics_list = "\n".join(f"- {t}" for t in (existing_topics or []))

        user_content = f"""SOURCE METADATA:
- Category: {category}
- Date: {date or 'unknown'}
- File type: {file_type}

SOURCE CONTENT:
{content}
"""
        if transcription:
            user_content += f"\nTRANSCRIPTION/DESCRIPTION:\n{transcription}\n"

        if topics_list:
            user_content += f"\nEXISTING WIKI TOPICS:\n{topics_list}\n"

        system_prompt = prompt

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        text = response.content[0].text
        return self._parse_json_response(text)

    async def answer_question(
        self,
        question: str,
        wiki_context: str,
    ) -> str:
        prompt = self._load_prompt("query_answer")

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=prompt,
            messages=[{
                "role": "user",
                "content": f"WIKI CONTEXT:\n{wiki_context}\n\nQUESTION:\n{question}",
            }],
        )
        return response.content[0].text

    async def describe_image(self, image_data: bytes, media_type: str = "image/jpeg") -> str:
        import base64
        encoded = base64.standard_b64encode(image_data).decode("utf-8")

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": "请详细描述这张图片。如果包含文字，请转录。识别其中的人物、地点、物品。说明可能的拍摄背景和时间。用中文回答。",
                    },
                ],
            }],
        )
        return response.content[0].text

    async def generate_cross_references(
        self,
        new_page_title: str,
        new_page_summary: str,
        existing_pages: list[dict],
    ) -> list[dict]:
        if not existing_pages:
            return []

        prompt = self._load_prompt("cross_reference")
        pages_text = "\n".join(
            f"- [{p['page_type']}] {p['title']} (slug: {p['slug']}): {p.get('summary', '')}"
            for p in existing_pages
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=0.2,
            system=prompt,
            messages=[{
                "role": "user",
                "content": f"NEW PAGE:\nTitle: {new_page_title}\nSummary: {new_page_summary}\n\nEXISTING PAGES:\n{pages_text}",
            }],
        )

        text = response.content[0].text
        result = self._parse_json_response(text)
        return result.get("cross_references", [])

    def _load_prompt(self, name: str) -> str:
        prompt_path = settings.data_dir.parent / "lifewiki" / "prompts" / f"{name}.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        prompts_dir = settings.data_dir.parent / "lifewiki" / "prompts"
        fallback = {
            "ingest_source": "You are a knowledge management assistant. Analyze the source and respond in JSON with keys: summary, topics, entities, timeline_events, cross_references, key_quotes.",
            "query_answer": "You are a knowledgeable assistant. Answer the question based on the wiki context provided. Cite relevant wiki pages.",
            "cross_reference": "You are a knowledge graph assistant. Identify relationships between pages. Respond in JSON with key: cross_references (list of {slug, relation_type, context}).",
        }
        return fallback.get(name, "You are a helpful assistant.")

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    return json.loads(text[json_start:json_end])
                except json.JSONDecodeError:
                    pass
            return {"raw_response": text}


llm_service = LLMService()
