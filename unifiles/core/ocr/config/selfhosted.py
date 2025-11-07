from loguru import logger

from .base import BaseConfig


class SelfHostedConfig(BaseConfig):
    """Configuration for self-hosted OCR (single instance, OpenAI-compatible API).

    Environment variables (single instance):
    - UNIFILES_SERVICE_OCR_SELFHOSTED_URL
    - UNIFILES_SERVICE_OCR_SELFHOSTED_MODEL
    - UNIFILES_SERVICE_OCR_SELFHOSTED_PROMPT
    - UNIFILES_SERVICE_OCR_SELFHOSTED_TEMPERATURE (optional, default: 0.7)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_TOKENS (optional, default: 2048)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_CONCURRENCY (optional, default: 5)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_RETRIES (optional, default: 2)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_REQUEST_TIMEOUT (optional, default: 120.0)
    """

    def __init__(self):
        super().__init__()
        self.url = self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_URL", "")
        self.model = self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_MODEL", "")
        self.prompt = self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_PROMPT", "")
        if self.prompt:
            with open(self.prompt, "r", encoding="utf-8") as f:
                self.prompt = f.read()

        self.temperature = float(self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_TEMPERATURE", "0.7"))
        self.max_tokens = int(self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_TOKENS", "2048"))

        self.api_key = self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_API_KEY", "")
        # Async processing configuration
        self.max_concurrency = int(self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_CONCURRENCY", "20"))
        self.max_retries = int(self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_MAX_RETRIES", "2"))
        self.request_timeout = float(self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_REQUEST_TIMEOUT", "120.0"))

    def validate(self) -> bool:
        if not self.url:
            logger.error("UNIFILES_SERVICE_OCR_SELFHOSTED_URL is not set.")
            return False
        if not self.model:
            logger.error("UNIFILES_SERVICE_OCR_SELFHOSTED_MODEL is not set.")
            return False
        if not (self.prompt and self.prompt.strip()):
            logger.error("UNIFILES_SERVICE_OCR_SELFHOSTED_PROMPT is not set.")
            return False
        return True

    def get_api_key(self) -> str:
        """Return API key if provided (optional)."""
        return self.api_key

    def get_model(self) -> str:
        return self.model

    def get_url(self) -> str:
        return self.url

    def get_prompt(self) -> str:
        return self.prompt

    def get_temperature(self) -> float:
        return self.temperature

    def get_max_tokens(self) -> int:
        return self.max_tokens

    def get_max_concurrency(self) -> int:
        return self.max_concurrency

    def get_max_retries(self) -> int:
        return self.max_retries

    def get_request_timeout(self) -> float:
        return self.request_timeout
