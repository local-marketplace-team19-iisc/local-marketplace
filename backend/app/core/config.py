from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Reads from environment (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./local_marketplace.db"
    # Direct Postgres connection for Alembic migrations (port 5432, no pooler).
    # Set to postgresql+psycopg://... Supabase direct URL. Not used at runtime.
    DATABASE_URL_DIRECT: str = ""

    # JWT settings
    JWT_SECRET: str = "your-secret-key-change-in-production"
    JWT_ACCESS_TOKEN_TTL_MINUTES: int = 60
    JWT_REFRESH_TOKEN_TTL_DAYS: int = 7
    JWT_ALGORITHM: str = "HS256"

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Rate limiting
    RATE_LIMIT_FAILED_LOGIN_ATTEMPTS: int = 5
    RATE_LIMIT_LOCKOUT_MINUTES: int = 15
    RATE_LIMIT_SIGNUP_PER_IP_HOUR: int = 10

    # ------------------------------------------------------------------ #
    # Feature 008 — SBERT intent router
    # ------------------------------------------------------------------ #
    # Path the SBERT loader checks for a pre-downloaded model snapshot. When
    # the directory contains a valid `sentence-transformers` snapshot the
    # loader uses it offline; otherwise see `ALLOW_MODEL_DOWNLOAD`.
    MODELS_DIR: str = "./models/sbert"
    # When `True`, the loader is allowed to fall back to a one-time
    # `sentence-transformers` download (network required). Defaults to
    # `False` so CI / corporate-firewall environments fail-fast rather than
    # hanging on a network call.
    ALLOW_MODEL_DOWNLOAD: bool = False
    # SBERT model identifier (Hugging Face id). `all-MiniLM-L6-v2` is ~80 MB,
    # English-only, fast on CPU. See spec §6 deferred — swap to the
    # `paraphrase-multilingual-MiniLM-L12-v2` if Hindi/Kannada/Tamil queries
    # become a v1.x requirement.
    SBERT_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Cosine-similarity threshold above which an utterance is bound to one
    # of the six labelled intents; below it the classifier returns
    # `unknown` (spec FR-1, FR-2). 0.35 is the empirically-tuned floor for
    # all-MiniLM-L6-v2 on this prototype set (Session 2 calibration): leaves
    # weather/music distractors below 0.20, keeps real intents above 0.35.
    INTENT_CONFIDENCE_THRESHOLD: float = 0.35
    # Threshold for the SBERT-based category match in entity extraction
    # (spec FR-3).
    CATEGORY_MATCH_THRESHOLD: float = 0.55
    # Hard ceiling (seconds) on one router turn before /api/chat returns a
    # friendly timeout bubble (HTTP 200, not 504). Carried over from the
    # feature 007 wiring; documented here so it survives the rewire.
    AGENT_CHAT_TURN_TIMEOUT_S: int = 20


settings = Settings()
