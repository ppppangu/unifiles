from loguru import logger

from .base import BaseConfig


class MistralConfig(BaseConfig):
    """Configuration class for Mistral OCR provider"""

    def __init__(self):
        super().__init__()
        self.api_key = self._get_env_var("MISTRAL_API_KEY")
        self.model = self._get_env_var("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

    def validate(self) -> bool:
        """Validate Mistral-specific configuration"""
        if not self.api_key:
            logger.error("Error: MISTRAL_API_KEY environment variable is not set.")
            logger.error(
                "Please set your API key: export MISTRAL_API_KEY=your_api_key_here"
            )
            return False
        return True

    def get_api_key(self) -> str:
        """Get the Mistral API key"""
        return self.api_key

    def get_model(self) -> str:
        """Get the Mistral OCR model name"""
        return self.model
