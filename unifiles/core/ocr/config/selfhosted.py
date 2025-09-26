from loguru import logger

from .base import BaseConfig


class SelfHostedConfig(BaseConfig):
    """Configuration for a self-hosted OCR HTTP service.

    Environment variables:
    - UNIFILES_SERVICE_OCR_SELFHOSTED_0_URL: Complete URL including endpoint, e.g. http://192.168.132.149:1288/infer

    Notes:
    - No authentication required
    - Prompt is required and read from env `UNIFILES_SERVICE_OCR_SELFHOSTED_0_PROMPT`
    """

    def __init__(self):
        super().__init__()
        self.url = self._get_env_var("UNIFILES_SERVICE_OCR_SELFHOSTED_0_URL", "")
        self.prompt = self._get_env_var(
            "UNIFILES_SERVICE_OCR_SELFHOSTED_0_PROMPT", ""
        )

    def validate(self) -> bool:
        if not self.url:
            logger.error("UNIFILES_SERVICE_OCR_SELFHOSTED_0_URL is not set.")
            return False
        if not (self.prompt and self.prompt.strip()):
            logger.error("UNIFILES_SERVICE_OCR_SELFHOSTED_0_PROMPT is not set.")
            return False
        return True

    def get_api_key(self) -> str:
        return ""

    def get_model(self) -> str:
        return "default"

    def get_url(self) -> str:
        return self.url

    def get_prompt(self) -> str:
        return self.prompt
