# MCP (Model Context Protocol) Integration

This document explains how to use MCP servers with Aegis-CLI agents to extend their capabilities with external tools.

## Overview

The Model Context Protocol (MCP) allows agents to access external tools and services. Aegis-CLI uses PydanticAI's native MCP integration to connect agents to MCP servers via:

- **Stdio Transport**: For local servers (e.g., `npx -y @modelcontextprotocol/server-github`)
- **SSE/HTTP Transport**: For remote servers (Server-Sent Events)

## Configuration

### 1. Create `mcp_config.json`

Create an `mcp_config.json` file in your project root with server configurations:

```json
{
  "servers": [
    {
      "name": "github",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    {
      "name": "google-search",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-google-search"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}",
        "GOOGLE_CSE_ID": "${GOOGLE_CSE_ID}"
      }
    },
    {
      "name": "custom-http-server",
      "transport": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_API_KEY}"
      }
    }
  ]
}
```

### 2. Set Environment Variables

Set the required environment variables referenced in the config:

```bash
export GITHUB_TOKEN="your_github_token"
export GOOGLE_API_KEY="your_google_api_key"
export GOOGLE_CSE_ID="your_custom_search_engine_id"
```

## Usage

### Basic Usage: Agent with MCP Tools

```python
from aegis.agents.coder import CoderAgent
from aegis.core.mcp_client import load_mcp_config, filter_servers_by_name

# Load and filter MCP servers
mcp_servers = load_mcp_config("mcp_config.json")
github_servers = filter_servers_by_name(mcp_servers, ["github"])

# Create agent with MCP servers
coder = CoderAgent()
coder.mcp_servers = github_servers

# Use agent with MCP tools
async with coder.run_with_mcp() as mcp_tools:
    # mcp_tools contains all tools from the GitHub MCP server
    # Use with PydanticAI Agent
    from pydantic_ai import Agent as PydanticAgent
    
    pydantic_agent = PydanticAgent(
        model="claude-3-5-sonnet-20241022",
        tools=mcp_tools,
        system_prompt=coder.get_system_prompt()
    )
    
    result = await pydantic_agent.run("Create a GitHub utility function")
```

### Orchestrator Pattern

The Orchestrator can selectively equip agents with MCP servers:

```python
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.coder import CoderAgent

# Create orchestrator with MCP config
orchestrator = OrchestratorAgent(mcp_config_path="mcp_config.json")

# Get appropriate servers for specific agent
coder_servers = orchestrator.get_mcp_servers_for_agent(
    "coder",
    server_names=["github", "google-search"]
)

# Equip CoderAgent with those servers
coder = CoderAgent()
coder.mcp_servers = coder_servers

# Agent now has access to GitHub and Google Search tools
async with coder.run_with_mcp() as mcp_tools:
    print(f"Available tools: {len(mcp_tools)}")
```

## Available MCP Servers

### GitHub Server
- **Package**: `@modelcontextprotocol/server-github`
- **Tools**: Repository management, issue tracking, PR operations
- **Setup**: Requires `GITHUB_TOKEN` environment variable

### Google Search Server
- **Package**: `@modelcontextprotocol/server-google-search`
- **Tools**: Web search capabilities
- **Setup**: Requires `GOOGLE_API_KEY` and `GOOGLE_CSE_ID`

### Custom Servers
You can create your own MCP servers following the [MCP specification](https://modelcontextprotocol.io/).

## Architecture

```
┌─────────────────────────────────────────────────┐
│            Aegis-CLI Application                │
└───────────────────┬─────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   BaseAgent           │
        │   - mcp_servers       │
        │   - run_with_mcp()    │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   MCPManager          │
        │   - run_servers()     │
        │   - get_tools()       │
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌──────────────┐        ┌──────────────┐
│ Stdio Server │        │ SSE Server   │
│ (Local)      │        │ (Remote)     │
└──────────────┘        └──────────────┘
```

## Examples

See `examples/mcp_example.py` for complete working examples:

```bash
python examples/mcp_example.py
```

## Troubleshooting

### Server Connection Issues

If MCP servers fail to connect:
1. Verify environment variables are set correctly
2. Check that `npx` is available for stdio servers
3. Ensure network connectivity for HTTP servers

### Missing Dependencies

Install MCP dependencies if not already installed:

```bash
pip install mcp pydantic-ai[mcp]
```

### Tool Discovery

To see available tools from a server:

```python
async with agent.run_with_mcp() as tools:
    for tool in tools:
        print(f"Tool: {tool.name}")
```
