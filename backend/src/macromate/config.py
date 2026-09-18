"""Runtime configuration, read from environment (see .env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="MACROMATE_", extra="ignore"
    )

    port: int = 8080
    log_level: str = "INFO"

    # See .env.example for why these two matter in deployment.
    mcp_stateless: bool = False
    allowed_hosts: str = "127.0.0.1,localhost"

    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


settings = Settings()
