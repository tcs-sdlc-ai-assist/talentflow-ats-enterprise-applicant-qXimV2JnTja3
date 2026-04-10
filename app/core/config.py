from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./talentflow.db"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    DEBUG: bool = False
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "Admin1234"
    SESSION_COOKIE_NAME: str = "talentflow_session"
    SESSION_MAX_AGE: int = 86400


settings = Settings()