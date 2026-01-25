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

from pydantic_ai.mcp import MCPServerStdio, MCPServerHTTP


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server.
    
    Attributes:
        name: Server name/identifier
        transport: Transport type ("stdio" or "http")
        command: Command to execute (for stdio transport)
        args: Command arguments (for stdio transport)
        env: Environment variables (for stdio transport)
        url: Server URL (for http transport)
        headers: HTTP headers (for http transport)
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
    
    Handles both stdio and HTTP transport types for MCP servers.
    Provides a context manager interface for managing server lifecycle.
    """
    
    def __init__(self, server_configs: list[MCPServerConfig]) -> None:
        """Initialize the MCP manager.
        
        Args:
            server_configs: List of MCP server configurations
        """
        self.server_configs = server_configs
        self._servers: list[MCPServerStdio | MCPServerHTTP] = []
        self._tools: list[Any] = []
    
    def _create_server(
        self, 
        config: MCPServerConfig
    ) -> MCPServerStdio | MCPServerHTTP:
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
        elif config.transport == "http":
            if not config.url:
                raise ValueError(
                    f"HTTP transport requires 'url' for server {config.name}"
                )
            return MCPServerHTTP(
                url=config.url,
                headers=config.headers if config.headers else None
            )
        else:
            raise ValueError(
                f"Unsupported transport type: {config.transport}. "
                "Must be 'stdio' or 'http'"
            )
    
    @asynccontextmanager
    async def run_servers(self) -> AsyncIterator[list[Any]]:
        """Context manager to run MCP servers and fetch tools.
        
        Initializes all configured servers, fetches their available tools,
        and ensures proper cleanup on exit.
        
        Yields:
            List of tools available from all connected servers
        """
        servers = []
        all_tools = []
        
        try:
            # Initialize all servers
            for config in self.server_configs:
                server = self._create_server(config)
                servers.append(server)
            
            # Start servers and collect tools
            for server in servers:
                async with server:
                    # Get tools from the server
                    # Note: The actual API might vary based on pydantic-ai version
                    # This is a placeholder for the tool fetching logic
                    tools = await server.get_tools()
                    all_tools.extend(tools)
            
            self._servers = servers
            self._tools = all_tools
            
            yield all_tools
            
        finally:
            # Cleanup is handled by the async context managers
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
        
        # Substitute environment variables in headers
        if "headers" in server_data and server_data["headers"]:
            headers_substituted = {}
            for key, value in server_data["headers"].items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var_name = value[2:-1]
                    env_value = os.environ.get(env_var_name, "")
                    headers_substituted[key] = value.replace(f"${{{env_var_name}}}", env_value)
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
