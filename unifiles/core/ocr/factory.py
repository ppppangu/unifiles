from typing import Dict, Type
from .base import BaseOCRProvider
from .providers.mistral import MistralOCRProvider
from .config.mistral import MistralConfig


class OCRProviderFactory:
    """Factory class for creating OCR provider instances"""
    
    _providers: Dict[str, Type[BaseOCRProvider]] = {
        'mistral': MistralOCRProvider,
    }
    
    _configs: Dict[str, Type] = {
        'mistral': MistralConfig,
    }
    
    @classmethod
    def create_provider(cls, provider_name: str = 'mistral', config=None) -> BaseOCRProvider:
        """Create an OCR provider instance
        
        Args:
            provider_name: Name of the provider (e.g., 'mistral')
            config: Optional configuration instance
            
        Returns:
            BaseOCRProvider: OCR provider instance
            
        Raises:
            ValueError: If provider_name is not supported
        """
        if provider_name not in cls._providers:
            raise ValueError(f"Unsupported OCR provider: {provider_name}. "
                           f"Supported providers: {list(cls._providers.keys())}")
        
        provider_class = cls._providers[provider_name]
        
        # If no config provided, create default config for the provider
        if config is None:
            config_class = cls._configs.get(provider_name)
            if config_class:
                config = config_class()
        
        return provider_class(config)
    
    @classmethod
    def get_supported_providers(cls) -> list:
        """Get list of supported provider names"""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseOCRProvider], config_class: Type = None):
        """Register a new OCR provider
        
        Args:
            name: Provider name
            provider_class: Provider class that inherits from BaseOCRProvider
            config_class: Optional config class for the provider
        """
        cls._providers[name] = provider_class
        if config_class:
            cls._configs[name] = config_class