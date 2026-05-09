from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    llm_api_base: str = "http://localhost:8000/v1"
    llm_api_key: str = "not-needed"
    llm_default_model: str = "gpt-4o"

    # Auth
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    # Database
    database_url: str = "sqlite+aiosqlite:///./agent_skills.db"

    # Storage
    skills_storage_path: str = "./storage/skills"
    workspace_storage_path: str = "./storage/workspace"

    # Logging
    logs_dir: str = "./logs"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
