from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Reads from environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 8000
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/local_marketplace"

    # JWT settings
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ACCESS_TOKEN_TTL_MINUTES: int = 60
    JWT_REFRESH_TOKEN_TTL_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # Rate limiting
    RATE_LIMIT_FAILED_LOGIN_ATTEMPTS: int = 5
    RATE_LIMIT_LOCKOUT_MINUTES: int = 15
    RATE_LIMIT_SIGNUP_PER_IP_HOUR: int = 10


settings = Settings()
