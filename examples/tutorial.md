# Aegis-CLI Tutorial

Welcome to Aegis-CLI! This tutorial will walk you through the basics of using the multi-agent framework.

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Basic Commands](#basic-commands)
4. [Understanding Agents](#understanding-agents)
5. [Working with Tools](#working-with-tools)
6. [Advanced Usage](#advanced-usage)

## Installation

### Prerequisites

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`

### Install with uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/aegis-cli.git
cd aegis-cli

# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

### Install with pip

```bash
pip install -e .
```

### Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_api_key_here
```

## Getting Started

### Your First Task

Let's start with a simple "Hello World" example:

```bash
aegis run "Create a hello world function"
```

This will:
1. Orchestrator analyzes your prompt
2. Coder generates the function
3. Tester creates and runs tests
4. Critic reviews the code
5. Results are saved to `.aegis/`

### Viewing Results

Check the reasoning trace:

```bash
ls .aegis/logs/
cat .aegis/logs/latest_log.md
```

View task history:

```bash
aegis history
```

Check current status:

```bash
aegis status
```

## Basic Commands

### Run a Task

```bash
aegis run "Your task description"
```

Options:
- `--verbose` or `-v`: Enable verbose output
- `--no-verify`: Skip verification cycle

### View History

```bash
aegis history --limit 20
```

### Show Status

```bash
aegis status
```

### List Available Agents

```bash
aegis agents
```

### List Available Tools

```bash
aegis tools
```

### Reset Session

```bash
aegis reset
```

This clears the database and logs. Use with caution!

## Understanding Agents

Aegis-CLI uses specialized agents that work together:

### Orchestrator Agent

- Analyzes user prompts
- Decomposes tasks into subtasks
- Manages dependencies
- Coordinates other agents

### Coder Agent

- Generates Python code
- Uses type hints and docstrings
- Follows PEP8 and best practices
- Responds to feedback from Tester and Critic

### Tester Agent

- Generates pytest tests
- Executes tests
- Parses failures
- Provides feedback to Coder

### Critic Agent

- Reviews code quality
- Checks for security issues
- Validates type hints and docstrings
- Ensures PEP8 compliance

### Janitor Agent

- Maintains documentation
- Updates README
- Syncs docstrings with code
- Cleans up unused imports

## Working with Tools

Tools provide functionality to agents:

### FileSystem Tool

Read, list, search files, and apply surgical edits:

```python
# Read a file
filesystem.execute(action="read_file", path="example.py")

# List directory
filesystem.execute(action="list_directory", path=".", pattern="*.py")

# Search content
filesystem.execute(action="search_content", pattern="def.*", path=".")

# Smart patch
filesystem.execute(action="smart_patch", path="file.py", changes=[...])
```

### Shell Tool

Execute safe shell commands:

```python
shell.execute(
    command=["pytest", "tests/"],
    require_confirmation=True,
    timeout=60
)
```

### Context Tool

Store and retrieve information:

```python
# Remember
context.execute(action="remember", key="user_id", value=123, agent="coder")

# Recall
context.execute(action="recall", key="user_id", agent="coder")

# Forget
context.execute(action="forget", key="user_id")
```

## Advanced Usage

### Verification Cycle

The verification cycle ensures code quality:

1. **Coder** generates code
2. **Tester** validates with tests
3. **Critic** reviews for quality/security
4. Loop until success or max retries
5. Escalate to human if needed

### Task Dependencies

Tasks can have dependencies:

```python
task1 = AgentTask(
    id="task1",
    type="code",
    payload={"description": "Create module"},
    dependencies=[]
)

task2 = AgentTask(
    id="task2",
    type="test",
    payload={"description": "Test module"},
    dependencies=["task1"]  # Waits for task1
)
```

### Custom System Prompts

Each agent has a system prompt that guides its behavior. You can customize these by modifying the agent classes.

### Reasoning Traces

All agent thoughts and actions are logged to `.aegis/logs/` in Markdown format:

```markdown
# Task Execution Log: user-task

**Task ID:** `12345678-1234-1234-1234-123456789abc`
**Started:** 2024-01-01 10:00:00

---

## [10:00:01] THOUGHT - Orchestrator

Analyzing prompt and decomposing into tasks

## [10:00:02] ACTION

**Tool:** `filesystem`
...
```

### Session Database

Task history is stored in `.aegis/session.db` (SQLite):

- Tasks with status and timestamps
- Tool calls with parameters and results
- Reasoning traces
- Agent memory with TTL

## Tips and Best Practices

1. **Be Specific**: Detailed prompts get better results
2. **Use Verbose Mode**: Add `-v` for debugging
3. **Review Logs**: Check `.aegis/logs/` for reasoning traces
4. **Iterate**: If first attempt fails, refine your prompt
5. **Monitor Status**: Use `aegis status` to track progress
6. **Reset When Needed**: Use `aegis reset` for a fresh start

## Troubleshooting

### "Command not found: aegis"

Make sure you've installed the package and activated the virtual environment.

### "API Key not found"

Set `ANTHROPIC_API_KEY` in your `.env` file.

### Tasks failing repeatedly

Check the logs in `.aegis/logs/` for detailed error messages.

### Database locked

Close other Aegis-CLI instances or use `aegis reset`.

## Next Steps

- Explore the [sample prompts](sample_prompts.md)
- Read the [architecture documentation](../README.md)
- Contribute to the project
- Join the community

## Getting Help

- GitHub Issues: Report bugs and request features
- Documentation: Read the comprehensive README
- Community: Join our Discord/Slack

Happy coding with Aegis-CLI! 🚀
