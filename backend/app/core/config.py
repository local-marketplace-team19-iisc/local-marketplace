from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Reads from environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 8000
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/local_marketplace"


settings = Settings()
