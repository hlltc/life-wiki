# LifeWiki

A personal life wiki powered by LLM, inspired by [Karpathy's llm-wiki](https://github.com/karpathy/llm-wiki).

## Features

- **AI-Powered Knowledge Base** — Ingest notes, articles, and documents; let the LLM organize and summarize them into wiki pages.
- **Wiki-Style Browsing** — Browse and navigate your knowledge base with a clean web interface.
- **Timeline View** — Explore your entries chronologically.
- **Full-Text Search** — Quickly find relevant pages.
- **Markdown Support** — Content rendered from Markdown with wiki-style linking.

## Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite (via aiosqlite)
- **LLM**: Anthropic Claude API
- **Frontend**: Jinja2 templates + vanilla JS
- **Python**: 3.10+

## Getting Started

```bash
# Install dependencies
uv sync

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-key-here"

# Run the server
uv run uvicorn lifewiki.main:app --reload
```

Visit `http://localhost:8000` to start using LifeWiki.

## Project Structure

```
lifewiki/
├── api/        # FastAPI route handlers
├── db/         # Database layer
├── models/     # Pydantic models
├── prompts/    # LLM prompt templates
├── services/   # Business logic
├── config.py   # App configuration
└── main.py     # App entry point
```

## License

MIT
