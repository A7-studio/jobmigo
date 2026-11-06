from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    database_url: str = "postgresql+asyncpg://jobmigo:jobmigo@localhost:5442/jobmigo"
    web_origin: str = "http://localhost:3000"
    better_auth_jwks_url: str = ""
    better_auth_issuer: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
