import re
from datetime import datetime
from pathlib import Path
from typing import Any

from lifewiki.config import settings
from lifewiki.models.source import WikiPage, TimelineEvent


def generate_wiki_page_markdown(
    title: str,
    page_type: str,
    summary: str,
    analysis: dict[str, Any],
    sources: list[dict] | None = None,
) -> str:
    lines = [
        f"# {title}",
        "",
        f"> **类型**: {page_type} | **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## 概述",
        "",
        summary,
        "",
    ]

    if analysis.get("timeline_events"):
        lines.extend(["## 时间线", ""])
        for evt in sorted(analysis["timeline_events"], key=lambda e: e.get("date", "")):
            date = evt.get("date", "未知日期")
            evt_title = evt.get("title", "")
            desc = evt.get("description", "")
            lines.append(f"- **{date}** {evt_title}" + (f" — {desc}" if desc else ""))
        lines.append("")

    if analysis.get("key_insights"):
        lines.extend(["## 关键洞察", ""])
        for insight in analysis["key_insights"]:
            lines.append(f"- {insight}")
        lines.append("")

    if analysis.get("entities"):
        lines.extend(["## 相关实体", ""])
        for entity in analysis["entities"]:
            name = entity.get("name", "")
            etype = entity.get("entity_type", "")
            desc = entity.get("description", "")
            slug = entity.get("slug", "")
            lines.append(f"- [[{slug}|{name}]] ({etype}) — {desc}")
        lines.append("")

    if analysis.get("cross_references"):
        lines.extend(["## 相关页面", ""])
        for ref in analysis["cross_references"]:
            slug = ref.get("target_slug", ref.get("slug", ""))
            context = ref.get("context", "")
            lines.append(f"- [[{slug}]] — {context}")
        lines.append("")

    if sources:
        lines.extend(["## 来源", ""])
        for src in sources:
            date = src.get("date", "")
            title_s = src.get("title", "")
            path = src.get("path", "")
            lines.append(f"- {date} [{title_s or path}]({path})")
        lines.append("")

    return "\n".join(lines)


def update_wiki_page_markdown(
    existing_content: str,
    new_analysis: dict[str, Any],
    source_title: str,
    source_date: str | None = None,
) -> str:
    new_section = f"\n## 来自来源: {source_title}"
    if source_date:
        new_section += f" ({source_date})"
    new_section += "\n"

    if new_analysis.get("summary"):
        new_section += f"\n{new_analysis['summary']}\n"

    if new_analysis.get("key_insights"):
        new_section += "\n### 关键要点\n"
        for insight in new_analysis["key_insights"]:
            new_section += f"- {insight}\n"

    if new_analysis.get("timeline_events"):
        new_section += "\n### 相关事件\n"
        for evt in new_analysis["timeline_events"]:
            date = evt.get("date", "")
            title = evt.get("title", "")
            new_section += f"- **{date}** {title}\n"

    new_section += "\n"
    return existing_content + new_section


def generate_index_markdown(pages: list[WikiPage]) -> str:
    lines = [
        "# LifeWiki 索引",
        "",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    topics = [p for p in pages if p.page_type == "topic"]
    entities = [p for p in pages if p.page_type == "entity"]

    if topics:
        lines.extend(["## 主题", ""])
        for p in sorted(topics, key=lambda x: x.title):
            summary = p.summary or ""
            lines.append(f"- [[{p.slug}|{p.title}]] — {summary} ({p.source_count} 个来源)")
        lines.append("")

    if entities:
        lines.extend(["## 实体", ""])
        for p in sorted(entities, key=lambda x: x.title):
            summary = p.summary or ""
            lines.append(f"- [[{p.slug}|{p.title}]] — {summary}")
        lines.append("")

    return "\n".join(lines)


def generate_log_entry(
    operation: str,
    source_title: str,
    source_path: str,
    result_summary: str,
) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"\n## [{date_str}] {operation} | {source_title}\n\n- 文件: `{source_path}`\n- 结果: {result_summary}\n"
