from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    data_dir: Path = Path("./data")
    db_path: Path = Path("./data/lifewiki.db")
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 4096
    claude_temperature: float = 0.3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def wiki_dir(self) -> Path:
        return self.data_dir / "wiki"

    @property
    def topics_dir(self) -> Path:
        return self.wiki_dir / "topics"

    @property
    def entities_dir(self) -> Path:
        return self.wiki_dir / "entities"


settings = Settings()
