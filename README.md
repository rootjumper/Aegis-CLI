"# Aegis-CLI

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> A modular, self-correcting multi-agent framework with advanced reasoning capabilities

## Overview

Aegis-CLI is a production-ready multi-agent framework that implements a "Plan-Execute-Verify" lifecycle for automated software development tasks. It uses specialized AI agents that collaborate to generate, test, review, and document code with minimal human intervention.

### Key Features

- 🤖 **Multi-Agent Architecture**: Specialized agents (Orchestrator, Coder, Critic, Tester, Janitor) work together
- 🔄 **Self-Correction Loop**: Automatic verification and retry with feedback incorporation
- 🧠 **Multi-LLM Support**: Use Anthropic, Google, Ollama, or LM Studio - [Configuration Guide](docs/LLM_CONFIGURATION.md)
- 🛡️ **Security-First**: Built-in security checks and safe command execution
- 📝 **Full Trace Logging**: Complete logging of tool calls, parameters, and agent interactions - [Logging Guide](FULL_TRACE_LOGGING.md)
- 💾 **Persistent Memory**: SQLite-based session management and agent memory
- 🎯 **Type-Safe**: Full Python 3.11+ type hints throughout
- 🧪 **Test-Driven**: Automatic test generation and validation
- 📚 **Documentation**: Automated documentation maintenance

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        USER PROMPT                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │   Orchestrator   │ ◄─── Task Decomposition
              │      Agent       │      & Delegation
              └────────┬─────────┘
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │  Coder   │ │  Tester  │ │  Critic  │
    │  Agent   │ │  Agent   │ │  Agent   │
    └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │
         └────────────┼────────────┘
                      │
              ┌───────▼────────┐
              │  Verification  │ ◄─── Self-Correction
              │     Cycle      │      Loop (max 3 retries)
              └───────┬────────┘
                      │
              ┌───────▼────────┐
              │    Janitor     │ ◄─── Documentation
              │     Agent      │      Maintenance
              └────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- At least one LLM provider:
  - Anthropic API key (recommended)
  - Google API key (Gemini)
  - Ollama server (local)
  - LM Studio (local)

### Installation

#### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/rootjumper/Aegis-CLI.git
cd Aegis-CLI

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS
.venv\Scripts\activate     # On Windows
```

#### Using pip

```bash
pip install -e .
```

### Configuration

Aegis-CLI supports multiple LLM providers. Configure at least one of the following:

#### Option 1: Anthropic (Claude) - Recommended

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and add your Anthropic API key:

```env
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # Optional, this is the default
DEFAULT_LLM_PROVIDER=anthropic  # Optional, this is the default
```

#### Option 2: Google (Gemini)

1. Get your Google AI API key from [Google AI Studio](https://aistudio.google.com/)

2. Add to your `.env`:

```env
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL=gemini-1.5-flash  # Optional, this is the default
DEFAULT_LLM_PROVIDER=google
```

#### Option 3: Ollama (Local)

1. Install and run [Ollama](https://ollama.ai/)

2. Pull a model (e.g., `ollama pull llama2`)

3. Add to your `.env`:

```env
OLLAMA_MODEL=llama2
OLLAMA_BASE_URL=http://localhost:11434/v1  # Optional, this is the default
DEFAULT_LLM_PROVIDER=ollama
```

#### Option 4: LM Studio (Local)

1. Install and run [LM Studio](https://lmstudio.ai/)

2. Load a model and start the local server

3. Add to your `.env`:

```env
LM_STUDIO_MODEL=your-local-model-name
LM_STUDIO_BASE_URL=http://localhost:1234/v1  # Optional, this is the default
DEFAULT_LLM_PROVIDER=lm_studio
```

#### Multi-Provider Setup

You can configure multiple providers and switch between them:

```env
# Configure multiple providers
ANTHROPIC_API_KEY=your_anthropic_key
GOOGLE_API_KEY=your_google_key
OLLAMA_MODEL=llama2

# Set default provider
DEFAULT_LLM_PROVIDER=anthropic  # or google, ollama, lm_studio
```

#### Additional Settings

```env
AEGIS_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
AEGIS_MAX_RETRIES=3
AEGIS_DB_PATH=.aegis/session.db
AEGIS_LOGS_PATH=.aegis/logs
```

### First Run

```bash
# Run a simple task
aegis run "Create a hello world function"

# View the results
aegis history

# Check reasoning traces
ls .aegis/logs/
```

## Usage

### Basic Commands

```bash
# Execute a task
aegis run "Your task description"

# With verbose output
aegis run "Task description" --verbose

# Skip verification cycle
aegis run "Task description" --no-verify

# View task history
aegis history --limit 20

# Show current status
aegis status

# List available agents
aegis agents

# List available tools
aegis tools

# Health check
aegis doctor

# Validate configuration
aegis validate

# Reset session (clears database and logs)
aegis reset
```

### Example Tasks

#### Code Generation

```bash
aegis run "Create a FastAPI endpoint for user authentication with JWT tokens"
```

#### Refactoring

```bash
aegis run "Refactor the database module to use async SQLAlchemy"
```

#### Bug Fixing

```bash
aegis run "Fix the memory leak in the file processing pipeline"
```

#### Testing

```bash
aegis run "Create comprehensive unit tests for the authentication module"
```

#### Documentation

```bash
aegis run "Update the README with installation instructions and usage examples"
```

See [examples/sample_prompts.md](examples/sample_prompts.md) for more examples.

## Project Structure

```
aegis-cli/
├── .aegis/                    # Runtime state (gitignored)
│   ├── session.db            # SQLite database
│   └── logs/                 # Reasoning traces
├── aegis/
│   ├── agents/               # Agent implementations
│   │   ├── base.py          # BaseAgent contract
│   │   ├── orchestrator.py  # Task decomposition
│   │   ├── coder.py         # Code generation
│   │   ├── critic.py        # Code review
│   │   ├── tester.py        # Test generation
│   │   └── janitor.py       # Documentation
│   ├── tools/                # Tool implementations
│   │   ├── base_tool.py     # Tool interface
│   │   ├── filesystem.py    # File operations
│   │   ├── shell.py         # Safe command execution
│   │   ├── context.py       # Memory management
│   │   └── registry.py      # Tool discovery
│   ├── core/                 # Core functionality
│   │   ├── state.py         # SQLite session manager
│   │   ├── logging.py       # Markdown trace writer
│   │   ├── verification.py  # Self-correction engine
│   │   └── feedback.py      # Error parsing
│   └── main.py              # CLI entry point
├── examples/
│   ├── sample_prompts.md    # Example prompts
│   └── tutorial.md          # Getting started guide
├── tests/                    # Test suite
├── .vscode/
│   └── tasks.json           # VS Code shortcuts
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Agents

### Orchestrator Agent

**Responsibility**: Task decomposition and coordination

- Analyzes user prompts
- Creates dependency graphs
- Delegates to specialized agents
- Manages verification cycle

### Coder Agent

**Responsibility**: Code generation

- Generates type-annotated Python code
- Follows PEP8 and best practices
- Uses surgical edits via smart_patch
- Incorporates feedback from Tester and Critic

### Critic Agent

**Responsibility**: Code review

- Checks PEP8 compliance
- Validates type hints
- Detects security vulnerabilities
- Reviews logic and patterns

### Tester Agent

**Responsibility**: Test generation and execution

- Generates pytest tests
- Executes tests via SafeShell
- Parses test failures
- Provides actionable feedback

### Janitor Agent

**Responsibility**: Documentation maintenance

- Updates README files
- Syncs docstrings with code
- Generates API documentation
- Cleans up unused imports

## Tools

Aegis-CLI includes 6 powerful built-in tools for agent operations:

### FileSystem Tool

File operations with comprehensive functionality:

- `read_file`: Read files with automatic encoding detection
- `write_file`: Write content to files with parent directory creation
- `delete_file`: Safely delete files
- `create_directory`: Create directories recursively
- `list_directory`: List files with glob pattern support
- `search_content`: Grep-like content search across files
- `smart_patch`: Apply surgical edits to files
- `file_exists`: Check file/directory existence

### Shell Tool

Safe command execution with security features:

- Whitelisted safe commands (git, pytest, pip, npm, docker, etc.)
- Human-in-the-loop confirmation for sensitive operations
- Timeout enforcement to prevent hanging
- Comprehensive output capture and parsing
- Support for 30+ development tools

### Context Tool

Agent memory management:

- `remember`: Store values in persistent agent memory
- `recall`: Retrieve stored values with agent filtering
- `forget`: Delete values from memory
- TTL-based automatic expiration
- Support for complex data structures

### Git Tool

Version control operations:

- `status`: Get repository status with parsed summary
- `diff`: Show file differences (staged/unstaged)
- `log`: View commit history with formatting
- `branch`: List or create branches
- `show`: Display commit details
- `add`: Stage files for commit
- `commit`: Create commits
- `current_branch`: Get active branch name

### Testing Tool

Test execution and analysis:

- `run_tests`: Execute pytest tests with detailed output
- `run_coverage`: Generate coverage reports with thresholds
- `list_tests`: Discover available tests
- `run_specific`: Run specific tests by name/pattern
- `validate_tests`: Check test structure and naming

### Python Tool

Python code analysis:

- `analyze_imports`: Parse and categorize import statements
- `lint`: Run pylint for code quality checks
- `type_check`: Execute mypy type checking
- `format_check`: Verify code formatting (black)
- `parse_syntax`: Validate Python syntax
- `get_functions`: Extract all function definitions
- `get_classes`: Extract class definitions with methods

For detailed usage examples, see [Tool Usage Guide](docs/TOOL_USAGE.md).

For developing custom tools, see [Tool Development Guide](docs/TOOL_DEVELOPMENT.md).

## Verification Cycle

The self-correction engine ensures code quality:

1. **Coder** generates code
2. **Tester** validates with tests (max 3 retries)
3. **Critic** reviews for quality/security (pass/fail)
4. Loop until SUCCESS or max_retries
5. Escalate to human if automated fix fails

**Exit Conditions**:
- Both Tester and Critic return SUCCESS
- Max retries exceeded (escalate)
- Human intervention requested

## Security Features

- Command whitelisting (no `rm -rf`, `sudo`, etc.)
- Path validation (prevents directory traversal)
- Secret detection in code review
- No `eval()` or `exec()` in generated code
- Input validation at all boundaries

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=aegis --cov-report=html

# Run specific test
pytest tests/test_agents.py -v
```

### Linting

```bash
# Run pylint
pylint aegis/

# Run mypy
mypy aegis/
```

### VS Code Integration

The project includes VS Code tasks for common operations:

- **Ctrl+Shift+A**: Run current prompt
- **Ctrl+Shift+H**: Show history
- **Ctrl+Shift+R**: Reset session

See `.vscode/tasks.json` for all available tasks.

## Logging and Traces

Aegis-CLI provides comprehensive logging at multiple levels:

### Full Trace Logging

All LLM interactions, tool calls, and agent actions are logged to `.aegis/llm_logs/` with complete details:

- **Tool calls made by LLMs** - See exactly which tools the AI decides to use
- **Complete parameters** - All arguments passed to tools with JSON formatting
- **Agent prompts and responses** - Full conversation history
- **File operations** - Detailed logging of filesystem changes

**Example log output:**
```
TOOL CALLS (2):
  [1] Tool Call:
      Name: filesystem
      ID: call_abc123
      Parameters:
        {
            "action": "write_file",
            "path": "app.py",
            "content": "from flask import Flask..."
        }
```

See the [Full Trace Logging Guide](FULL_TRACE_LOGGING.md) for complete documentation.

### Reasoning Traces

Task-level execution logs are stored in `.aegis/logs/` in Markdown format:

```markdown
# Task Execution Log: user-task

**Task ID:** `abc123...`
**Started:** 2024-01-01 10:00:00

---

## [10:00:01] THOUGHT - Orchestrator

Analyzing prompt and decomposing into tasks

## [10:00:02] ACTION

**Tool:** `filesystem`
**Parameters:**
```json
{"action": "read_file", "path": "example.py"}
```
```

## Session Database

Task history is stored in `.aegis/session.db` (SQLite):

- **tasks**: Task metadata and status
- **tool_calls**: Tool invocations with results
- **reasoning_traces**: Agent reasoning logs
- **agent_memory**: Persistent agent memory with TTL

## Configuration Reference

Aegis-CLI can be configured through environment variables in the `.env` file:

### LLM Provider Configuration

Choose one or more LLM providers:

```env
# Anthropic (Claude)
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # Default model

# Google (Gemini)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL=gemini-1.5-flash  # Default model

# Ollama (Local)
OLLAMA_MODEL=llama2
OLLAMA_BASE_URL=http://localhost:11434/v1  # Default URL

# LM Studio (Local)
LM_STUDIO_MODEL=your-local-model
LM_STUDIO_BASE_URL=http://localhost:1234/v1  # Default URL

# Default provider selection
DEFAULT_LLM_PROVIDER=anthropic  # or google, ollama, lm_studio
```

### Application Settings

```env
AEGIS_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
AEGIS_MAX_RETRIES=3           # Maximum retry attempts
AEGIS_DB_PATH=.aegis/session.db
AEGIS_LOGS_PATH=.aegis/logs
```

## Troubleshooting

### Common Issues

**"Command not found: aegis"**
- Ensure virtual environment is activated
- Run `uv sync` or `pip install -e .`

**"API Key not found"** or **"No LLM providers configured"**
- Set at least one LLM provider in `.env` file:
  - `ANTHROPIC_API_KEY` for Claude
  - `GOOGLE_API_KEY` for Gemini
  - `OLLAMA_MODEL` for Ollama
  - `LM_STUDIO_MODEL` for LM Studio
- Check that your `.env` file is in the project root
- Verify your API keys are valid

**"Database locked"**
- Close other Aegis-CLI instances
- Use `aegis reset` if needed

**Tasks failing repeatedly**
- Check logs in `.aegis/logs/` for details
- Ensure prompts are specific and clear
- Verify API key is valid

### Getting Help

- 📖 Read the [Tutorial](examples/tutorial.md)
- 💡 Check [Sample Prompts](examples/sample_prompts.md)
- 🐛 Report bugs on [GitHub Issues](https://github.com/rootjumper/Aegis-CLI/issues)

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure linting passes
5. Submit a pull request

### Code Standards

- Python 3.11+ with type hints
- PEP8 compliance (enforced by pylint)
- Google-style docstrings
- Test coverage > 80%
- Security-first mindset

## Roadmap

- [x] Multi-model support (Anthropic, Google, Ollama, LM Studio)
- [ ] Additional LLM providers (OpenAI, Cohere, etc.)
- [ ] Additional language support (JavaScript, Go, Rust)
- [ ] Web UI for task monitoring
- [ ] Plugin system for custom agents
- [ ] Distributed execution
- [ ] Advanced caching and optimization

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [PydanticAI](https://github.com/pydantic/pydantic-ai)
- Supports multiple LLM providers:
  - [Anthropic Claude](https://www.anthropic.com/)
  - [Google Gemini](https://ai.google.dev/)
  - [Ollama](https://ollama.ai/)
  - [LM Studio](https://lmstudio.ai/)
- CLI framework by [Typer](https://typer.tiangolo.com/)
- Beautiful terminal UI with [Rich](https://rich.readthedocs.io/)

## Citation

If you use Aegis-CLI in your research or project, please cite:

```bibtex
@software{aegis_cli,
  title = {Aegis-CLI: A Modular Multi-Agent Framework},
  author = {Aegis Team},
  year = {2024},
  url = {https://github.com/rootjumper/Aegis-CLI}
}
```

---

Made with ❤️ by the Aegis Team" 
