"""Tests for LLM configuration and model factory."""

import os
import pytest
from unittest.mock import patch, MagicMock

from aegis.core.llm_config import (
    LLMProviderConfig,
    LLMConfig,
    load_llm_config_from_env,
    create_model,
    get_default_model,
    get_model_for_provider,
)
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIChatModel


class TestLLMProviderConfig:
    """Test LLMProviderConfig model."""
    
    def test_create_anthropic_config(self) -> None:
        """Test creating Anthropic configuration."""
        config = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key="test-key"
        )
        
        assert config.provider == "anthropic"
        assert config.model_name == "claude-3-5-sonnet-20241022"
        assert config.api_key == "test-key"
        assert config.base_url is None
        assert config.default is False
    
    def test_create_ollama_config(self) -> None:
        """Test creating Ollama configuration."""
        config = LLMProviderConfig(
            provider="ollama",
            model_name="llama2",
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        
        assert config.provider == "ollama"
        assert config.model_name == "llama2"
        assert config.base_url == "http://localhost:11434/v1"


class TestLLMConfig:
    """Test LLMConfig model."""
    
    def test_get_default_config_by_flag(self) -> None:
        """Test getting default config by default flag."""
        config1 = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key="key1"
        )
        config2 = LLMProviderConfig(
            provider="google",
            model_name="gemini-1.5-flash",
            api_key="key2",
            default=True
        )
        
        llm_config = LLMConfig(providers=[config1, config2])
        default = llm_config.get_default_config()
        
        assert default is not None
        assert default.provider == "google"
    
    def test_get_default_config_by_default_provider(self) -> None:
        """Test getting default config by default_provider setting."""
        config1 = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key="key1"
        )
        config2 = LLMProviderConfig(
            provider="google",
            model_name="gemini-1.5-flash",
            api_key="key2"
        )
        
        llm_config = LLMConfig(
            providers=[config1, config2],
            default_provider="google"
        )
        default = llm_config.get_default_config()
        
        assert default is not None
        assert default.provider == "google"
    
    def test_get_default_config_fallback(self) -> None:
        """Test falling back to first provider."""
        config = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key="key1"
        )
        
        llm_config = LLMConfig(
            providers=[config],
            default_provider="google"  # Not available
        )
        default = llm_config.get_default_config()
        
        assert default is not None
        assert default.provider == "anthropic"
    
    def test_get_provider_config(self) -> None:
        """Test getting specific provider configuration."""
        config1 = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key="key1"
        )
        config2 = LLMProviderConfig(
            provider="google",
            model_name="gemini-1.5-flash",
            api_key="key2"
        )
        
        llm_config = LLMConfig(providers=[config1, config2])
        
        google_config = llm_config.get_provider_config("google")
        assert google_config is not None
        assert google_config.provider == "google"
        
        missing_config = llm_config.get_provider_config("ollama")
        assert missing_config is None


class TestLoadLLMConfigFromEnv:
    """Test loading LLM configuration from environment."""
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022"
    }, clear=True)
    def test_load_anthropic_only(self) -> None:
        """Test loading Anthropic configuration only."""
        config = load_llm_config_from_env()
        
        assert len(config.providers) == 1
        assert config.providers[0].provider == "anthropic"
        assert config.providers[0].api_key == "test-anthropic-key"
        assert config.providers[0].model_name == "claude-3-5-sonnet-20241022"
    
    @patch.dict(os.environ, {
        "GOOGLE_API_KEY": "test-google-key",
        "GOOGLE_MODEL": "gemini-1.5-pro"
    }, clear=True)
    def test_load_google_only(self) -> None:
        """Test loading Google configuration only."""
        config = load_llm_config_from_env()
        
        assert len(config.providers) == 1
        assert config.providers[0].provider == "google"
        assert config.providers[0].api_key == "test-google-key"
        assert config.providers[0].model_name == "gemini-1.5-pro"
    
    @patch.dict(os.environ, {
        "OLLAMA_MODEL": "llama2",
        "OLLAMA_BASE_URL": "http://server:11434/v1"
    }, clear=True)
    def test_load_ollama_only(self) -> None:
        """Test loading Ollama configuration only."""
        config = load_llm_config_from_env()
        
        assert len(config.providers) == 1
        assert config.providers[0].provider == "ollama"
        assert config.providers[0].model_name == "llama2"
        assert config.providers[0].base_url == "http://server:11434/v1"
    
    @patch.dict(os.environ, {
        "LM_STUDIO_MODEL": "local-model",
        "LM_STUDIO_BASE_URL": "http://localhost:1234/v1"
    }, clear=True)
    def test_load_lm_studio_only(self) -> None:
        """Test loading LM Studio configuration only."""
        config = load_llm_config_from_env()
        
        assert len(config.providers) == 1
        assert config.providers[0].provider == "lm_studio"
        assert config.providers[0].model_name == "local-model"
        assert config.providers[0].base_url == "http://localhost:1234/v1"
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "anthropic-key",
        "GOOGLE_API_KEY": "google-key",
        "OLLAMA_MODEL": "llama2",
        "DEFAULT_LLM_PROVIDER": "google"
    }, clear=True)
    def test_load_multiple_providers(self) -> None:
        """Test loading multiple provider configurations."""
        config = load_llm_config_from_env()
        
        assert len(config.providers) == 3
        
        providers = {p.provider for p in config.providers}
        assert "anthropic" in providers
        assert "google" in providers
        assert "ollama" in providers
        
        assert config.default_provider == "google"
    
    @patch.dict(os.environ, {
        "GOOGLE_API_KEY": "google-key"
    }, clear=True)
    def test_default_model_names(self) -> None:
        """Test that default model names are used when not specified."""
        config = load_llm_config_from_env()
        
        assert config.providers[0].model_name == "gemini-1.5-flash"


class TestCreateModel:
    """Test model creation from configuration."""
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
    def test_create_anthropic_model(self) -> None:
        """Test creating Anthropic model."""
        config = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022",
            api_key="test-key"
        )
        
        model = create_model(config)
        
        assert isinstance(model, AnthropicModel)
    
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=True)
    def test_create_google_model(self) -> None:
        """Test creating Google model."""
        config = LLMProviderConfig(
            provider="google",
            model_name="gemini-1.5-flash",
            api_key="test-key"
        )
        
        model = create_model(config)
        
        assert isinstance(model, GeminiModel)
    
    def test_create_ollama_model(self) -> None:
        """Test creating Ollama model."""
        config = LLMProviderConfig(
            provider="ollama",
            model_name="llama2",
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        
        model = create_model(config)
        
        assert isinstance(model, OpenAIChatModel)
    
    def test_create_lm_studio_model(self) -> None:
        """Test creating LM Studio model."""
        config = LLMProviderConfig(
            provider="lm_studio",
            model_name="local-model",
            base_url="http://localhost:1234/v1",
            api_key="lm-studio"
        )
        
        model = create_model(config)
        
        assert isinstance(model, OpenAIChatModel)
    
    def test_create_model_missing_api_key(self) -> None:
        """Test that creating model without API key raises error."""
        config = LLMProviderConfig(
            provider="anthropic",
            model_name="claude-3-5-sonnet-20241022"
        )
        
        with pytest.raises(ValueError, match="Anthropic API key is required"):
            create_model(config)
    
    def test_create_model_missing_base_url(self) -> None:
        """Test that creating local model without base_url raises error."""
        config = LLMProviderConfig(
            provider="ollama",
            model_name="llama2"
        )
        
        with pytest.raises(ValueError, match="Ollama base_url is required"):
            create_model(config)


class TestGetDefaultModel:
    """Test getting default model."""
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022"
    }, clear=True)
    def test_get_default_model_success(self) -> None:
        """Test getting default model when providers are configured."""
        model = get_default_model()
        
        assert isinstance(model, AnthropicModel)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_default_model_no_providers(self) -> None:
        """Test that getting default model without providers raises error."""
        with pytest.raises(ValueError, match="No LLM providers configured"):
            get_default_model()


class TestGetModelForProvider:
    """Test getting model for specific provider."""
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key",
        "GOOGLE_API_KEY": "test-key2"
    }, clear=True)
    def test_get_model_for_provider_success(self) -> None:
        """Test getting model for specific provider."""
        model = get_model_for_provider("google")
        
        assert isinstance(model, GeminiModel)
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-key"
    }, clear=True)
    def test_get_model_for_provider_not_configured(self) -> None:
        """Test that getting unconfigured provider raises error."""
        with pytest.raises(ValueError, match="Provider 'google' is not configured"):
            get_model_for_provider("google")
