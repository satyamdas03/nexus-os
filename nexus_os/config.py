"""Settings and environment configuration for NEXUS OS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file="~/.nexus-os/env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    default_model: str = Field(default="claude-sonnet-5")
    vendor_dir: Path = Field(default=Path(__file__).resolve().parent.parent / "vendor" / "agency-agents")
    config_dir: Path = Field(default=Path.home() / ".nexus-os")
    auto_commit: bool = Field(default=True)

    @field_validator("vendor_dir", "config_dir", mode="before")
    @classmethod
    def _expand_paths(cls, value: Any) -> Path:
        if isinstance(value, str):
            value = os.path.expanduser(value)
            return Path(value)
        if isinstance(value, Path):
            return value
        raise ValueError(f"Expected Path or str, got {type(value)}")

    def ensure_dirs(self) -> None:
        """Create global config directories if missing."""
        self.config_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings
