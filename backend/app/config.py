"""Application configuration."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Tenerife Tourism Intelligence"
    app_version: str = "0.1.0"
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "tourism.db"
    models_dir: Path = data_dir / "models"

    # Raw data source (override with TOURISM_RAW_DATA_DIR env var)
    raw_data_dir: Path = base_dir / "data" / "raw"

    # Database
    database_url: str = ""

    # CORS
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")
    ]

    # API
    api_prefix: str = "/api"

    # Scheduler
    scheduler_enabled: bool = True

    model_config = {"env_prefix": "TOURISM_"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.database_url:
            self.database_url = f"sqlite:///{self.db_path}"


settings = Settings()
