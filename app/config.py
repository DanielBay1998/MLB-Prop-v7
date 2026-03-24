from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "MLB Prop Predictor"
    env: str = "dev"
    secret_key: str = "change-me"

    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/mlb_props"
    redis_url: str = "redis://redis:6379/0"
    result_backend: str = "redis://redis:6379/1"

    mlb_stats_api_base: str = "https://statsapi.mlb.com/api/v1"
    odds_api_key: str | None = None
    odds_api_base: str = "https://api.the-odds-api.com/v4"
    odds_regions: str = "us"
    weather_api_base: str = "https://api.open-meteo.com/v1/forecast"

    default_lookback_games: int = 30
    cache_ttl_seconds: int = 900
    model_dir: str = str(BASE_DIR / "artifacts" / "models")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
