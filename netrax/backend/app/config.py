"""
NETRA-X Configuration
Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "NETRA-X"
    APP_VERSION: str = "1.0.0-phase1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://netrax:netrax_secret@localhost:5432/netrax_db"
    DATABASE_URL_SYNC: str = "postgresql://netrax:netrax_secret@localhost:5432/netrax_db"

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # OCR
    OCR_ENABLED: bool = True
    TESSERACT_CMD: Optional[str] = None

    # NLP / NER
    NER_MODEL: str = "en_core_web_sm"

    # LLM (Optional)
    LLM_ENABLED: bool = False
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"

    # Security
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Processing
    BACKGROUND_WORKERS: int = 2

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
