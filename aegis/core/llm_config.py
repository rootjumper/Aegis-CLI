"""LLM configuration and model factory for Aegis-CLI.

This module handles configuration and creation of different LLM providers:
- Anthropic (Claude)
- Google (Gemini)
- Ollama (local, OpenAI-compatible)
- LM Studio (local, OpenAI-compatible)
"""

import os
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


LLMProviderType = Literal["anthropic", "google", "ollama", "lm_studio"]


class LLMProviderConfig(BaseModel):
    """Configuration for an LLM provider.

    Attributes:
        provider: Provider type
        model_name: Name of the model to use
        api_key: API key (optional for local providers)
        base_url: Base URL for API (used by local providers)
        default: Whether this is the default provider
    """
    provider: LLMProviderType
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    default: bool = False


class LLMConfig(BaseModel):
    """Global LLM configuration.

    Attributes:
        providers: List of configured LLM providers
        default_provider: Name of default provider to use
    """
    providers: list[LLMProviderConfig] = Field(default_factory=list)
    default_provider: LLMProviderType = "anthropic"

    def get_default_config(self) -> LLMProviderConfig | None:
        """Get the default provider configuration.

        Returns:
            Default provider config or None if not found
        """
        # First, try to find provider marked as default
        for config in self.providers:
            if config.default:
                return config

        # Fall back to default_provider setting
        for config in self.providers:
            if config.provider == self.default_provider:
                return config

        # Return first provider if available
        if self.providers:
            return self.providers[0]

        return None

    def get_provider_config(
        self,
        provider: LLMProviderType
    ) -> LLMProviderConfig | None:
        """Get configuration for a specific provider.

        Args:
            provider: Provider type to get config for

        Returns:
            Provider config or None if not found
        """
        for config in self.providers:
            if config.provider == provider:
                return config
        return None


def load_llm_config_from_env() -> LLMConfig:
    """Load LLM configuration from environment variables.

    Reads configuration from environment variables:
    - ANTHROPIC_API_KEY: Anthropic API key
    - ANTHROPIC_MODEL: Anthropic model name (default: claude-3-5-sonnet-20241022)
    - GOOGLE_API_KEY: Google API key
    - GOOGLE_MODEL: Google model name (default: gemini-1.5-flash)
    - OLLAMA_BASE_URL: Ollama server URL (default: http://localhost:11434/v1)
    - OLLAMA_MODEL: Ollama model name (default: llama2)
    - LM_STUDIO_BASE_URL: LM Studio server URL (default: http://localhost:1234/v1)
    - LM_STUDIO_MODEL: LM Studio model name
    - DEFAULT_LLM_PROVIDER: Default provider to use (default: anthropic)

    Returns:
        LLM configuration
    """
    providers: list[LLMProviderConfig] = []

    # Anthropic configuration
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        providers.append(LLMProviderConfig(
            provider="anthropic",
            model_name=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=anthropic_api_key
        ))

    # Google configuration
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        providers.append(LLMProviderConfig(
            provider="google",
            model_name=os.getenv("GOOGLE_MODEL", "gemini-1.5-flash"),
            api_key=google_api_key
        ))

    # Ollama configuration
    ollama_model = os.getenv("OLLAMA_MODEL")
    if ollama_model:
        providers.append(LLMProviderConfig(
            provider="ollama",
            model_name=ollama_model,
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama"  # Ollama doesn't require real API key
        ))

    # LM Studio configuration
    lm_studio_model = os.getenv("LM_STUDIO_MODEL")
    if lm_studio_model:
        providers.append(LLMProviderConfig(
            provider="lm_studio",
            model_name=lm_studio_model,
            base_url=os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
            api_key="lm-studio"  # LM Studio doesn't require real API key
        ))

    # Determine default provider
    default_provider_str = os.getenv("DEFAULT_LLM_PROVIDER", "anthropic")

    # Validate provider type
    valid_providers: tuple[str, ...] = ("anthropic", "google", "ollama", "lm_studio")
    if default_provider_str not in valid_providers:
        default_provider_str = "anthropic"

    default_provider: LLMProviderType = default_provider_str  # type: ignore

    return LLMConfig(
        providers=providers,
        default_provider=default_provider
    )


def create_model(config: LLMProviderConfig) -> Model:
    """Create a PydanticAI Model from provider configuration.

    Args:
        config: Provider configuration

    Returns:
        PydanticAI Model instance

    Raises:
        ValueError: If provider type is unsupported or configuration is invalid
    """
    if config.provider == "anthropic":
        if not config.api_key:
            raise ValueError("Anthropic API key is required")

        # Set environment variable for PydanticAI to use
        os.environ["ANTHROPIC_API_KEY"] = config.api_key
        return AnthropicModel(config.model_name)

    if config.provider == "google":
        if not config.api_key:
            raise ValueError("Google API key is required")

        # Set environment variable for PydanticAI to use
        os.environ["GEMINI_API_KEY"] = config.api_key
        return GeminiModel(config.model_name)

    if config.provider == "ollama":
        if not config.base_url:
            raise ValueError("Ollama base_url is required")

        # Create OpenAI-compatible provider for Ollama
        ollama_provider = OpenAIProvider(
            base_url=config.base_url,
            api_key=config.api_key or "ollama"
        )

        # Type ignore needed: using custom model name for local Ollama models
        return OpenAIChatModel(
            config.model_name,
            provider=ollama_provider  # type: ignore[arg-type]
        )

    if config.provider == "lm_studio":
        if not config.base_url:
            raise ValueError("LM Studio base_url is required")

        # Create OpenAI-compatible provider for LM Studio
        lm_studio_provider = OpenAIProvider(
            base_url=config.base_url,
            api_key=config.api_key or "lm-studio"
        )

        # Type ignore needed: using custom model name for local LM Studio models
        return OpenAIChatModel(
            config.model_name,
            provider=lm_studio_provider  # type: ignore[arg-type]
        )

    raise ValueError(f"Unsupported provider: {config.provider}")


def get_default_model() -> Model:
    """Get the default model based on environment configuration.

    Returns:
        Default PydanticAI Model instance

    Raises:
        ValueError: If no providers are configured
    """
    llm_config = load_llm_config_from_env()

    default_config = llm_config.get_default_config()
    if not default_config:
        raise ValueError(
            "No LLM providers configured. Please set at least one of: "
            "ANTHROPIC_API_KEY, GOOGLE_API_KEY, OLLAMA_MODEL, LM_STUDIO_MODEL"
        )

    return create_model(default_config)


def get_model_for_provider(provider: LLMProviderType) -> Model:
    """Get a model for a specific provider.

    Args:
        provider: Provider type

    Returns:
        PydanticAI Model instance for the provider

    Raises:
        ValueError: If provider is not configured
    """
    llm_config = load_llm_config_from_env()

    provider_config = llm_config.get_provider_config(provider)
    if not provider_config:
        raise ValueError(f"Provider '{provider}' is not configured")

    return create_model(provider_config)
