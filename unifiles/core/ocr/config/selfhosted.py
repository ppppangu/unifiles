from loguru import logger

from .base import BaseConfig


class SelfHostedConfig(BaseConfig):
    """Configuration for self-hosted OCR service with OpenAI-compatible API.

    Supports multimodal models deployed via vLLM or other OpenAI-compatible servers.
    Examples: Qwen3-VL, Qwen2-VL, etc.

    Environment variables (X = instance number: 0, 1, 2, ...):
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_URL: API endpoint URL
      Example: http://localhost:8012/v1/chat/completions
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_MODEL: Model name (must match server's served model name)
      Example: qwen3vl-2b
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_PROMPT: OCR prompt text
      Example: 请识别图片中的所有文字内容，使用 Markdown 格式输出
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_TEMPERATURE: Generation temperature (optional, default: 0.7)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_MAX_TOKENS: Maximum tokens to generate (optional, default: 2048)

    Notes:
    - Uses OpenAI chat completion format
    - Images are automatically base64 encoded
    - No authentication required (add if needed on server side)
    """

    def __init__(self, instance_id: int = 0):
        super().__init__()
        self.instance_id = instance_id
        prefix = f"UNIFILES_SERVICE_OCR_SELFHOSTED_{instance_id}_"

        self.url = self._get_env_var(f"{prefix}URL", "")
        self.model = self._get_env_var(f"{prefix}MODEL", "")
        self.prompt = self._get_env_var(f"{prefix}PROMPT", "")
        self.temperature = float(self._get_env_var(f"{prefix}TEMPERATURE", "0.7"))
        self.max_tokens = int(self._get_env_var(f"{prefix}MAX_TOKENS", "2048"))

    def validate(self) -> bool:
        if not self.url:
            logger.error(
                f"UNIFILES_SERVICE_OCR_SELFHOSTED_{self.instance_id}_URL is not set."
            )
            return False
        if not self.model:
            logger.error(
                f"UNIFILES_SERVICE_OCR_SELFHOSTED_{self.instance_id}_MODEL is not set."
            )
            return False
        if not (self.prompt and self.prompt.strip()):
            logger.error(
                f"UNIFILES_SERVICE_OCR_SELFHOSTED_{self.instance_id}_PROMPT is not set."
            )
            return False
        return True

    def get_api_key(self) -> str:
        """No API key required for self-hosted service"""
        return ""

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
