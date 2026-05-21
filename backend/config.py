from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    slack_bot_token: str = ""
    slack_signing_secret: str = ""

    database_url: str = "sqlite+aiosqlite:///./procurement.db"
    chroma_persist_dir: str = "./data/chroma"
    knowledge_base_dir: str = "./data/knowledge_base"
    seed_dir: str = "./data/seed"
    dashboard_base_url: str = "http://localhost:5173"

    default_pilot_team: str = "pilot-alpha"
    prompt_library_version: str = "v1.0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = '["http://localhost:5173","http://localhost:3000"]'

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.cors_origins)
        except Exception:
            return ["http://localhost:5173"]


settings = Settings()
