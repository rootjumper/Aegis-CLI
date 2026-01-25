"""MCP (Model Context Protocol) client manager.

This module provides integration with MCP servers to enable agents to use
external tools via the Model Context Protocol.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from pydantic import BaseModel, Field

from pydantic_ai.mcp import MCPServerStdio, MCPServerSSE


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server.

    Attributes:
        name: Server name/identifier
        transport: Transport type ("stdio", "http", or "sse")
        command: Command to execute (for stdio transport)
        args: Command arguments (for stdio transport)
        env: Environment variables (for stdio transport)
        url: Server URL (for http/sse transport)
        headers: HTTP headers (for http/sse transport)
    """
    name: str
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class MCPManager:
    """Manager for MCP server connections and tools.

    Handles both stdio and SSE transport types for MCP servers.
    Provides a context manager interface for managing server lifecycle.
    """

    def __init__(self, server_configs: list[MCPServerConfig]) -> None:
        """Initialize the MCP manager.

        Args:
            server_configs: List of MCP server configurations
        """
        self.server_configs = server_configs
        self._servers: list[MCPServerStdio | MCPServerSSE] = []
        self._tools: list[Any] = []

    def _create_server(
        self,
        config: MCPServerConfig
    ) -> MCPServerStdio | MCPServerSSE:
        """Create an MCP server instance from configuration.

        Args:
            config: Server configuration

        Returns:
            MCP server instance

        Raises:
            ValueError: If transport type is unsupported or config is invalid
        """
        if config.transport == "stdio":
            if not config.command:
                raise ValueError(
                    f"Stdio transport requires 'command' for server {config.name}"
                )
            return MCPServerStdio(
                command=config.command,
                args=config.args,
                env=config.env if config.env else None
            )

        if config.transport in ("http", "sse"):
            if not config.url:
                raise ValueError(
                    f"SSE/HTTP transport requires 'url' for server {config.name}"
                )
            return MCPServerSSE(
                url=config.url,
                headers=config.headers if config.headers else None
            )

        raise ValueError(
            f"Unsupported transport type: {config.transport}. "
            "Must be 'stdio', 'http', or 'sse'"
        )

    @asynccontextmanager
    async def run_servers(self) -> AsyncIterator[list[MCPServerStdio | MCPServerSSE]]:
        """Context manager to run MCP servers.

        Initializes all configured servers and ensures proper cleanup on exit.
        The servers should be passed to PydanticAI Agent's toolsets parameter.

        Yields:
            List of MCP server instances that can be used as toolsets

        Example:
            ```python
            from pydantic_ai import Agent

            async with mcp_manager.run_servers() as mcp_servers:
                agent = Agent(
                    model="claude-3-5-sonnet",
                    toolsets=mcp_servers,  # Pass MCP servers as toolsets
                    system_prompt="..."
                )
                result = await agent.run("Your prompt")
            ```
        """
        servers: list[MCPServerStdio | MCPServerSSE] = []

        try:
            # Initialize all servers
            for config in self.server_configs:
                server = self._create_server(config)
                servers.append(server)

            self._servers = servers

            # Yield servers to be used as toolsets with PydanticAI
            yield servers

        finally:
            # Cleanup
            self._servers = []
            self._tools = []

    async def get_tools(self) -> list[Any]:
        """Get the list of available tools from all servers.

        Returns:
            List of tool instances
        """
        return self._tools.copy()

    def get_server_names(self) -> list[str]:
        """Get the names of all configured servers.

        Returns:
            List of server names
        """
        return [config.name for config in self.server_configs]


def load_mcp_config(config_path: str | Path | None = None) -> list[MCPServerConfig]:
    """Load MCP server configuration from a JSON file.

    Supports environment variable substitution in the format ${VAR_NAME}.

    Args:
        config_path: Path to the MCP configuration file.
                    Defaults to 'mcp_config.json' in the current directory.

    Returns:
        List of MCPServerConfig instances

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid
    """
    # pylint: disable=too-many-branches
    if config_path is None:
        config_path = Path("mcp_config.json")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"MCP config file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in MCP config file: {e}") from e

    if "servers" not in config_data:
        raise ValueError("MCP config must contain 'servers' key")

    # Parse server configs and substitute environment variables
    server_configs = []
    for server_data in config_data["servers"]:
        # Substitute environment variables in env dict
        if "env" in server_data and server_data["env"]:
            env_substituted = {}
            for key, value in server_data["env"].items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var_name = value[2:-1]
                    env_value = os.environ.get(env_var_name, "")
                    env_substituted[key] = env_value
                else:
                    env_substituted[key] = value
            server_data["env"] = env_substituted

        # Substitute environment variables in headers (using same logic as env)
        if "headers" in server_data and server_data["headers"]:
            headers_substituted = {}
            for key, value in server_data["headers"].items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var_name = value[2:-1]
                    env_value = os.environ.get(env_var_name, "")
                    headers_substituted[key] = env_value
                else:
                    headers_substituted[key] = value
            server_data["headers"] = headers_substituted

        server_configs.append(MCPServerConfig(**server_data))

    return server_configs


def filter_servers_by_name(
    servers: list[MCPServerConfig],
    names: list[str]
) -> list[MCPServerConfig]:
    """Filter servers by name.

    Args:
        servers: List of all server configurations
        names: List of server names to include

    Returns:
        List of filtered server configurations
    """
    return [server for server in servers if server.name in names]
