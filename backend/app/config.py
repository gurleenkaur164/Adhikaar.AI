"""Application configuration.

All secrets/tuning come from environment variables so the same code runs on a
laptop (SQLite, no keys) or on Render (PostgreSQL + Groq) with zero edits.
"""
import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        # --- AI (Groq / Llama 3) ---------------------------------------
        # If GROQ_API_KEY is unset, the extraction agent transparently falls
        # back to a deterministic rule-based parser so the app runs at Rs. 0.
        self.GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
        self.GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        # --- Database --------------------------------------------------
        # Defaults to a local SQLite file. Set DATABASE_URL to a Postgres
        # connection string (postgresql+psycopg://...) in production.
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL", "sqlite:///./adhikar.db"
        )

        # --- CORS ------------------------------------------------------
        self.CLIENT_URL: str = os.getenv("CLIENT_URL", "http://localhost:3000")

        self.APP_NAME: str = "Adhikar.AI"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.GROQ_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
