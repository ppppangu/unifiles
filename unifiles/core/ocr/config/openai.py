from loguru import logger

from .base import BaseConfig


class OpenAIConfig(BaseConfig):
    """Configuration for OpenAI OCR (single instance, async SDK).

    User options kept minimal: URL, API_KEY, MODEL, PROMPT.
    Other behaviors (timeouts/concurrency) are internal defaults.
    """

    def __init__(self):
        super().__init__()
        # Single-instance, non-indexed env variables
        self.url = self._get_env_var("UNIFILES_SERVICE_OCR_OPENAI_URL", "")
        self.api_key = self._get_env_var("UNIFILES_SERVICE_OCR_OPENAI_API_KEY", "")
        self.model = self._get_env_var("UNIFILES_SERVICE_OCR_OPENAI_MODEL", "")
        self.prompt = self._get_env_var("UNIFILES_SERVICE_OCR_OPENAI_PROMPT", "")

        # Trimmed: generation and concurrency knobs are internal constants now

    def validate(self) -> bool:
        """Validate that all required configuration is present."""
        if not self.url:
            logger.error("UNIFILES_SERVICE_OCR_OPENAI_URL is not set.")
            return False
        if not self.api_key:
            logger.error("UNIFILES_SERVICE_OCR_OPENAI_API_KEY is not set.")
            return False
        if not self.model:
            logger.error("UNIFILES_SERVICE_OCR_OPENAI_MODEL is not set.")
            return False
        if not (self.prompt and self.prompt.strip()):
            logger.error("UNIFILES_SERVICE_OCR_OPENAI_PROMPT is not set.")
            return False
        return True

    def get_api_key(self) -> str:
        """Get the API key for authentication."""
        return self.api_key

    def get_model(self) -> str:
        """Get the model name."""
        return self.model

    def get_url(self) -> str:
        """Get the API endpoint URL."""
        return self.url

    def get_prompt(self) -> str:
        """Get the OCR prompt text."""
        return self.prompt

    # The following parameters are intentionally not exposed via env
    # and should be controlled internally by the provider implementation.
