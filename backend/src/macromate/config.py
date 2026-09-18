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

    # Nutrition data sources
    usda_api_key: str = "I70E4v7AZe2eb51OYvvOiHq7ocbyxFdtcUK650lo"  # Required for Task 6; stub search_nutrition works without it

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/macromate"

    # OAuth (Alexa+ account-linking — required before add-on deployment)
    oauth_client_id: str = "macromate-alexa"
    oauth_client_secret: str = ""
    oauth_issuer: str = ""  # Set to your App Runner URL before deploying

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


settings = Settings()
