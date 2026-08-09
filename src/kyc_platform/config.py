from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="KYC_", extra="ignore")

    app_name: str = "KYC Compliance Platform"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/kyc.db"
    data_dir: Path = Path("data")
    output_dir: Path = Path("outputs")
    offline: bool = True
    log_level: str = "INFO"
    risk_policy_path: Path = Path("config/risk-policy.v1.json")
    benchmark_dataset_path: Path = Path("datasets/benchmark-v1")
    sanctions_review_threshold: float = Field(default=0.72, ge=0, le=1)
    sanctions_match_threshold: float = Field(default=0.86, ge=0, le=1)
    external_request_timeout_seconds: float = Field(default=30.0, gt=0)

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
