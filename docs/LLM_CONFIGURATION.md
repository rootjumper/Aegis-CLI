# Multi-LLM Provider Configuration Guide

Aegis-CLI supports multiple Large Language Model (LLM) providers, giving you flexibility to choose the best option for your needs. This guide provides detailed configuration instructions for each supported provider.

## Supported Providers

- **Anthropic (Claude)** - Cloud-based, high-quality reasoning
- **Google (Gemini)** - Cloud-based, multimodal capabilities
- **Ollama** - Self-hosted, privacy-focused, runs on your own hardware
- **LM Studio** - Desktop application for running local models

## Quick Start

1. Choose at least one LLM provider from the options below
2. Follow the setup instructions for your chosen provider(s)
3. Copy `.env.example` to `.env`
4. Add your provider configuration to `.env`
5. Run `aegis run "your task"`

## Provider Setup Instructions

### Anthropic (Claude)

**Recommended for: Production use, high-quality outputs**

#### Setup

1. Sign up at [Anthropic Console](https://console.anthropic.com/)
2. Create an API key
3. Add to `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
DEFAULT_LLM_PROVIDER=anthropic
```

#### Available Models

- `claude-3-5-sonnet-20241022` (recommended) - Best balance of speed and quality
- `claude-3-opus-20240229` - Highest quality, slower
- `claude-3-haiku-20240307` - Fastest, lower cost

#### Pricing

- Sonnet: ~$3 per million input tokens, ~$15 per million output tokens
- See [Anthropic Pricing](https://www.anthropic.com/pricing) for current rates

---

### Google (Gemini)

**Recommended for: Multimodal tasks, Google ecosystem integration**

#### Setup

1. Get API key from [Google AI Studio](https://aistudio.google.com/)
2. Add to `.env`:

```env
GOOGLE_API_KEY=your-google-api-key-here
GOOGLE_MODEL=gemini-1.5-flash
DEFAULT_LLM_PROVIDER=google
```

#### Available Models

- `gemini-1.5-flash` (recommended) - Fast and efficient
- `gemini-1.5-pro` - Higher quality, slower
- `gemini-2.0-flash-exp` - Experimental latest features

#### Pricing

- Flash: Free tier available, then ~$0.075 per million tokens
- See [Google AI Pricing](https://ai.google.dev/pricing) for current rates

---

### Ollama (Local)

**Recommended for: Privacy, offline use, no API costs**

#### Setup

1. Install Ollama from [ollama.ai](https://ollama.ai/)

2. Pull a model:
   ```bash
   ollama pull llama2
   # or
   ollama pull mistral
   # or
   ollama pull codellama
   ```

3. Start Ollama (usually runs automatically after installation)

4. Add to `.env`:

```env
OLLAMA_MODEL=llama2
OLLAMA_BASE_URL=http://localhost:11434/v1
DEFAULT_LLM_PROVIDER=ollama
```

#### Available Models

Popular models (run `ollama list` to see installed models):
- `llama2` - Good general purpose model
- `codellama` - Optimized for code generation
- `mistral` - Fast and capable
- `phi` - Small but capable, runs on lower-end hardware
- `deepseek-coder` - Excellent for coding tasks

See [Ollama Library](https://ollama.ai/library) for full list.

#### Network Configuration

**For Ollama running on another machine:**

```env
OLLAMA_BASE_URL=http://your-server-ip:11434/v1
```

For example, if Ollama is running on a server at `192.168.1.100`:

```env
OLLAMA_BASE_URL=http://192.168.1.100:11434/v1
```

#### Hardware Requirements

- **Minimum**: 8GB RAM for 7B parameter models
- **Recommended**: 16GB+ RAM for 13B parameter models
- **GPU**: Optional but significantly improves performance

---

### LM Studio (Local)

**Recommended for: Desktop use, GUI for model management**

#### Setup

1. Download and install [LM Studio](https://lmstudio.ai/)

2. In LM Studio:
   - Download a model from the search interface
   - Click "Start Server" in the local server tab
   - Note the model identifier and port

3. Add to `.env`:

```env
LM_STUDIO_MODEL=your-model-identifier
LM_STUDIO_BASE_URL=http://localhost:1234/v1
DEFAULT_LLM_PROVIDER=lm_studio
```

#### Model Identifier

The model identifier is shown in LM Studio's server tab. Common formats:
- `local-model`
- `TheBloke/Llama-2-7B-Chat-GGUF`
- `codellama-7b-instruct.Q4_K_M.gguf`

#### Network Configuration

If running LM Studio on another machine:

```env
LM_STUDIO_BASE_URL=http://your-computer-ip:1234/v1
```

---

## Multi-Provider Configuration

You can configure multiple providers and switch between them:

```env
# Configure all providers
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=your-google-key
OLLAMA_MODEL=llama2
LM_STUDIO_MODEL=local-model

# Set which one to use by default
DEFAULT_LLM_PROVIDER=anthropic  # or google, ollama, lm_studio

# Optional: customize models
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
GOOGLE_MODEL=gemini-1.5-pro
```

### Switching Providers

To switch providers, update `DEFAULT_LLM_PROVIDER` in your `.env` file:

```env
DEFAULT_LLM_PROVIDER=ollama  # Switch to Ollama
```

Then restart Aegis-CLI or run a new command.

## Troubleshooting

### "No LLM providers configured"

- Ensure you have at least one provider configured in `.env`
- Check that your `.env` file is in the project root directory
- Verify the environment variable names are correct

### Anthropic: "API Key not found"

- Verify `ANTHROPIC_API_KEY` is set correctly in `.env`
- Check that your API key starts with `sk-ant-`
- Ensure your API key has not expired

### Google: "API Key not found" or "GEMINI_API_KEY"

- Set `GOOGLE_API_KEY` in `.env`
- Get your key from [Google AI Studio](https://aistudio.google.com/)

### Ollama: Connection refused

- Verify Ollama is running: `ollama list`
- Check the base URL matches Ollama's server
- Ensure the port (default 11434) is accessible
- For network access, check firewall settings

### LM Studio: Connection refused

- Verify LM Studio's server is started
- Check the port (default 1234) in LM Studio matches `.env`
- Ensure a model is loaded in LM Studio

### Performance Issues with Local Models

- Ensure you have sufficient RAM
- Close other memory-intensive applications
- Consider using smaller models (e.g., 7B instead of 13B parameters)
- Enable GPU acceleration if available

## Best Practices

### For Development

- Use local models (Ollama/LM Studio) to avoid API costs
- Use smaller, faster models for rapid iteration
- Switch to cloud providers for final validation

### For Production

- Use Anthropic or Google for reliability and quality
- Set up error handling for API rate limits
- Monitor API usage and costs

### For Privacy-Sensitive Work

- Use Ollama or LM Studio for complete data privacy
- Ensure models run entirely on your infrastructure
- No data is sent to external servers

## Model Selection Guide

| Use Case | Recommended Provider | Model |
|----------|---------------------|-------|
| General tasks | Anthropic | claude-3-5-sonnet-20241022 |
| Code generation | Anthropic or Ollama | claude-3-5-sonnet or codellama |
| Fast iterations | Google | gemini-1.5-flash |
| Privacy-critical | Ollama | llama2 or mistral |
| Offline work | Ollama or LM Studio | Any local model |
| Cost-conscious | Ollama or LM Studio | Any local model (free) |
| Multimodal | Google | gemini-1.5-pro |

## Advanced Configuration

### Custom Model Settings

For provider-specific settings, you can modify the model configuration in the code:

```python
from aegis.core.llm_config import get_model_for_provider

# Get a specific provider's model
model = get_model_for_provider("ollama")
```

### Per-Agent Model Selection

Different agents can use different models:

```python
from aegis.agents.coder import CoderAgent
from aegis.core.llm_config import get_model_for_provider

# Use Ollama for the coder agent
ollama_model = get_model_for_provider("ollama")
coder = CoderAgent(model=ollama_model)
```

## Getting Help

If you encounter issues:

1. Check this guide's troubleshooting section
2. Review the main [README.md](../README.md)
3. Check provider-specific documentation
4. Open an issue on [GitHub](https://github.com/rootjumper/Aegis-CLI/issues)

## Contributing

Found a way to improve these configurations or support for a new provider? Contributions are welcome!
