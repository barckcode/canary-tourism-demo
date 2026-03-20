"""Application configuration."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


def _read_version() -> str:
    """Read version from the VERSION file at the repository root."""
    version_file = Path(__file__).resolve().parent.parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


class Settings(BaseSettings):
    app_name: str = "Tenerife Tourism Intelligence"
    app_version: str = _read_version()
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "tourism.db"
    models_dir: Path = data_dir / "models"

    # Raw data source (override with TOURISM_RAW_DATA_DIR env var)
    raw_data_dir: Path = base_dir.parent / "tenerife-tourism-data"

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
