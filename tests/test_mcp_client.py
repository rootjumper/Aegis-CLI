"""Tests for MCP client functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from aegis.core.mcp_client import (
    MCPServerConfig,
    MCPManager,
    load_mcp_config,
    filter_servers_by_name
)


def test_mcp_server_config_stdio() -> None:
    """Test creating an MCP server config for stdio transport."""
    config = MCPServerConfig(
        name="test-server",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": "test_token"}
    )
    
    assert config.name == "test-server"
    assert config.transport == "stdio"
    assert config.command == "npx"
    assert len(config.args) == 2
    assert config.env["GITHUB_TOKEN"] == "test_token"


def test_mcp_server_config_http() -> None:
    """Test creating an MCP server config for SSE transport."""
    config = MCPServerConfig(
        name="test-sse-server",
        transport="sse",
        url="http://localhost:8000/mcp",
        headers={"Authorization": "Bearer test_token"}
    )
    
    assert config.name == "test-sse-server"
    assert config.transport == "sse"
    assert config.url == "http://localhost:8000/mcp"
    assert config.headers["Authorization"] == "Bearer test_token"


def test_mcp_manager_initialization() -> None:
    """Test MCPManager initialization."""
    configs = [
        MCPServerConfig(
            name="server1",
            transport="stdio",
            command="test"
        ),
        MCPServerConfig(
            name="server2",
            transport="sse",
            url="http://localhost:8000"
        )
    ]
    
    manager = MCPManager(configs)
    assert len(manager.server_configs) == 2
    assert manager.get_server_names() == ["server1", "server2"]


def test_load_mcp_config_not_found() -> None:
    """Test loading MCP config when file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_mcp_config("/nonexistent/path/mcp_config.json")


def test_load_mcp_config_valid() -> None:
    """Test loading valid MCP config."""
    config_data = {
        "servers": [
            {
                "name": "github",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "test"}
            },
            {
                "name": "sse-server",
                "transport": "sse",
                "url": "http://localhost:8000/mcp"
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        servers = load_mcp_config(temp_path)
        assert len(servers) == 2
        assert servers[0].name == "github"
        assert servers[0].transport == "stdio"
        assert servers[1].name == "sse-server"
        assert servers[1].transport == "sse"
    finally:
        Path(temp_path).unlink()


def test_load_mcp_config_invalid_json() -> None:
    """Test loading invalid JSON config."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_mcp_config(temp_path)
    finally:
        Path(temp_path).unlink()


def test_load_mcp_config_missing_servers_key() -> None:
    """Test loading config without 'servers' key."""
    config_data = {"other_key": "value"}
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="must contain 'servers' key"):
            load_mcp_config(temp_path)
    finally:
        Path(temp_path).unlink()


def test_load_mcp_config_env_substitution() -> None:
    """Test environment variable substitution in config."""
    import os
    
    # Set test environment variable
    os.environ["TEST_TOKEN"] = "my_test_token"
    
    config_data = {
        "servers": [
            {
                "name": "test",
                "transport": "stdio",
                "command": "test",
                "env": {"TOKEN": "${TEST_TOKEN}"}
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f)
        temp_path = f.name
    
    try:
        servers = load_mcp_config(temp_path)
        assert servers[0].env["TOKEN"] == "my_test_token"
    finally:
        Path(temp_path).unlink()
        del os.environ["TEST_TOKEN"]


def test_filter_servers_by_name() -> None:
    """Test filtering servers by name."""
    servers = [
        MCPServerConfig(name="github", transport="stdio", command="test"),
        MCPServerConfig(name="google", transport="stdio", command="test"),
        MCPServerConfig(name="custom", transport="sse", url="http://test")
    ]
    
    filtered = filter_servers_by_name(servers, ["github", "custom"])
    assert len(filtered) == 2
    assert filtered[0].name == "github"
    assert filtered[1].name == "custom"


def test_filter_servers_by_name_empty() -> None:
    """Test filtering with no matches."""
    servers = [
        MCPServerConfig(name="github", transport="stdio", command="test")
    ]
    
    filtered = filter_servers_by_name(servers, ["nonexistent"])
    assert len(filtered) == 0


def test_mcp_manager_create_stdio_server() -> None:
    """Test creating stdio server from config."""
    config = MCPServerConfig(
        name="test",
        transport="stdio",
        command="npx",
        args=["-y", "test-server"]
    )
    
    manager = MCPManager([config])
    server = manager._create_server(config)
    
    # Should create MCPServerStdio instance
    from pydantic_ai.mcp import MCPServerStdio
    assert isinstance(server, MCPServerStdio)


def test_mcp_manager_create_http_server() -> None:
    """Test creating SSE server from config."""
    config = MCPServerConfig(
        name="test",
        transport="sse",
        url="http://localhost:8000/mcp"
    )
    
    manager = MCPManager([config])
    server = manager._create_server(config)
    
    # Should create MCPServerSSE instance
    from pydantic_ai.mcp import MCPServerSSE
    assert isinstance(server, MCPServerSSE)


def test_mcp_manager_create_server_invalid_transport() -> None:
    """Test creating server with invalid transport."""
    config = MCPServerConfig(
        name="test",
        transport="invalid",
        command="test"
    )
    
    manager = MCPManager([config])
    
    with pytest.raises(ValueError, match="Unsupported transport type"):
        manager._create_server(config)


def test_mcp_manager_create_stdio_server_missing_command() -> None:
    """Test creating stdio server without command."""
    config = MCPServerConfig(
        name="test",
        transport="stdio"
    )
    
    manager = MCPManager([config])
    
    with pytest.raises(ValueError, match="requires 'command'"):
        manager._create_server(config)


def test_mcp_manager_create_http_server_missing_url() -> None:
    """Test creating SSE server without URL."""
    config = MCPServerConfig(
        name="test",
        transport="sse"
    )
    
    manager = MCPManager([config])
    
    with pytest.raises(ValueError, match="requires 'url'"):
        manager._create_server(config)
