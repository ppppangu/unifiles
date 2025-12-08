from .base import BaseConfig


class SimpleOCRConfig(BaseConfig):
    """Configuration for the built-in pdfplumber-based simple provider.

    This provider does not require any external credentials. The class exists to
    keep the factory interface uniform with other providers.
    """

    def validate(self) -> bool:
        return True

    def get_api_key(self) -> str:
        return ""

    def get_model(self) -> str:
        # Keep a meaningful identifier for logging/metrics
        return "pdfplumber"
