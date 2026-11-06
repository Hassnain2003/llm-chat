from __future__ import annotations

import json

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    @field_validator("api_keys")
    @classmethod
    def validate_api_keys(cls, value: str) -> str:
        if not value:
            return value
        parsed = json.loads(value)
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(limit, int) and limit > 0
            for key, limit in parsed.items()
        ):
            raise ValueError("API_KEYS values must be positive integer requests-per-minute limits")
        return value

    model_backend_url: str = "http://localhost:11434"  # Ollama local default
    model_name: str = "tinyllama"
    backend_type: str = "ollama"  # ollama | vllm
    rate_limit_per_minute: int = 60
    api_keys: str = ""
    rate_limit_bucket_ttl_seconds: int = 600
    rate_limit_max_buckets: int = 10000
    queue_max_depth: int = 100
    request_timeout: int = 120

    @property
    def api_key_limits(self) -> dict[str, int]:
        if not self.api_keys:
            return {}
        try:
            parsed = json.loads(self.api_keys)
        except json.JSONDecodeError as exc:
            raise ValueError("API_KEYS must be a JSON object mapping keys to limits") from exc
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, int) and value > 0
            for key, value in parsed.items()
        ):
            raise ValueError("API_KEYS values must be positive integer requests-per-minute limits")
        return parsed


settings = Settings()
