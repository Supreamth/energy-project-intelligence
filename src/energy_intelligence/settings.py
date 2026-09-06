"""Runtime settings. Secrets stay in environment, never in git."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hermes@127.0.0.1:55432/intelligence"
    object_store_dir: str = "var/objects"


settings = Settings()
