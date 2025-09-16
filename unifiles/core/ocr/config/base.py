import os
from abc import ABC, abstractmethod
from dotenv import load_dotenv

load_dotenv()


class BaseConfig(ABC):
    """Base configuration class for OCR providers"""
    
    def __init__(self):
        self._load_environment()
    
    def _load_environment(self):
        """Load environment variables - can be overridden by subclasses"""
        load_dotenv()
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate the configuration"""
        pass
    
    @abstractmethod
    def get_api_key(self) -> str:
        """Get the API key"""
        pass
    
    @abstractmethod
    def get_model(self) -> str:
        """Get the model name"""
        pass
    
    def _get_env_var(self, key: str, default: str = None) -> str:
        """Helper method to get environment variables"""
        return os.getenv(key, default)