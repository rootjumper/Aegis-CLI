"""Tests for BaseAgent MCP integration."""

import pytest

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse
from aegis.core.mcp_client import MCPServerConfig


class MockAgent(BaseAgent):
    """Mock agent implementation for testing."""
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a task."""
        return AgentResponse(
            status="SUCCESS",
            data={},
            reasoning_trace="Test processing"
        )
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate input."""
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt."""
        return "Test agent"
    
    def get_required_tools(self) -> list[str]:
        """Get required tools."""
        return []


def test_base_agent_initialization_no_mcp() -> None:
    """Test BaseAgent initialization without MCP servers."""
    agent = MockAgent(name="test-agent")
    
    assert agent.name == "test-agent"
    assert agent.mcp_servers == []
    assert agent._mcp_manager is None


def test_base_agent_initialization_with_mcp() -> None:
    """Test BaseAgent initialization with MCP servers."""
    mcp_servers = [
        MCPServerConfig(
            name="test-server",
            transport="stdio",
            command="test"
        )
    ]
    
    agent = MockAgent(name="test-agent", mcp_servers=mcp_servers)
    
    assert agent.name == "test-agent"
    assert len(agent.mcp_servers) == 1
    assert agent.mcp_servers[0].name == "test-server"


def test_base_agent_get_mcp_server_names() -> None:
    """Test getting MCP server names."""
    mcp_servers = [
        MCPServerConfig(name="server1", transport="stdio", command="test"),
        MCPServerConfig(name="server2", transport="sse", url="http://test")
    ]
    
    agent = MockAgent(name="test-agent", mcp_servers=mcp_servers)
    
    names = agent.get_mcp_server_names()
    assert names == ["server1", "server2"]


def test_base_agent_get_mcp_server_names_empty() -> None:
    """Test getting MCP server names when none configured."""
    agent = MockAgent(name="test-agent")
    
    names = agent.get_mcp_server_names()
    assert names == []


def test_base_agent_mcp_servers_assignment() -> None:
    """Test assigning MCP servers after initialization."""
    agent = MockAgent(name="test-agent")
    
    assert agent.mcp_servers == []
    
    mcp_servers = [
        MCPServerConfig(name="github", transport="stdio", command="npx")
    ]
    
    agent.mcp_servers = mcp_servers
    
    assert len(agent.mcp_servers) == 1
    assert agent.mcp_servers[0].name == "github"
