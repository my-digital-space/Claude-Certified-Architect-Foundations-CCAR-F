"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
import secrets

from dotenv import load_dotenv

# Load .env file from the project root (claude-mock-api/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


class Settings:
    """Central configuration.  Reads from env vars, falls back to defaults."""

    def __init__(self) -> None:
        self.mock_api_key: str = os.getenv("MOCK_API_KEY", "mock-api-key-change-me")
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.claude_cli_path: str = os.getenv("CLAUDE_CLI_PATH", "claude")
        self.max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))
        self.allowed_origins: list[str] = [
            o.strip()
            for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")
            if o.strip()
        ]

    # --- runtime key rotation (in-memory only) ---

    def rotate_api_key(self) -> str:
        """Generate a new random API key and return it."""
        new_key = f"mock-{secrets.token_urlsafe(32)}"
        self.mock_api_key = new_key
        return new_key


# Singleton used across the app
settings = Settings()
