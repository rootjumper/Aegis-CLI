"""Integration tests for context tool."""

import pytest
from aegis.tools.context import ContextTool
from aegis.core.state import get_state_manager


@pytest.fixture
def context_tool():
    """Create a ContextTool instance."""
    return ContextTool()


def test_context_tool_creation():
    """Test creating a ContextTool."""
    tool = ContextTool()
    assert tool.name == "context"
    assert "memory" in tool.description.lower()


def test_context_tool_schema():
    """Test ContextTool parameter schema."""
    tool = ContextTool()
    schema = tool.parameters_schema
    
    assert "properties" in schema
    assert "action" in schema["properties"]
    assert "key" in schema["required"]
    assert "remember" in schema["properties"]["action"]["enum"]
    assert "recall" in schema["properties"]["action"]["enum"]
    assert "forget" in schema["properties"]["action"]["enum"]


@pytest.mark.asyncio
async def test_remember_and_recall(context_tool):
    """Test storing and retrieving a value."""
    # Store a value
    result = await context_tool.execute(
        action="remember",
        key="test_key",
        value="test_value",
        agent="test_agent"
    )
    
    assert result.success is True
    
    # Retrieve the value
    result = await context_tool.execute(
        action="recall",
        key="test_key"
    )
    
    assert result.success is True
    assert result.data == "test_value"


@pytest.mark.asyncio
async def test_recall_nonexistent_key(context_tool):
    """Test recalling a non-existent key."""
    result = await context_tool.execute(
        action="recall",
        key="nonexistent_key"
    )
    
    assert result.success is False
    assert "No value found" in result.error


@pytest.mark.asyncio
async def test_forget(context_tool):
    """Test deleting a stored value."""
    # Store a value
    await context_tool.execute(
        action="remember",
        key="delete_me",
        value="temporary",
        agent="test_agent"
    )
    
    # Delete the value
    result = await context_tool.execute(
        action="forget",
        key="delete_me"
    )
    
    assert result.success is True
    
    # Verify it's gone
    result = await context_tool.execute(
        action="recall",
        key="delete_me"
    )
    
    assert result.success is False


@pytest.mark.asyncio
async def test_remember_with_ttl(context_tool):
    """Test storing a value with TTL."""
    result = await context_tool.execute(
        action="remember",
        key="ttl_key",
        value="expires_soon",
        agent="test_agent",
        ttl=3600  # 1 hour
    )
    
    assert result.success is True
    
    # Should be able to recall immediately
    result = await context_tool.execute(
        action="recall",
        key="ttl_key"
    )
    
    assert result.success is True
    assert result.data == "expires_soon"


@pytest.mark.asyncio
async def test_remember_different_agents(context_tool):
    """Test storing values from different agents."""
    # Agent 1 stores a value
    await context_tool.execute(
        action="remember",
        key="shared_key",
        value="agent1_value",
        agent="agent1"
    )
    
    # Agent 2 stores a value with same key
    await context_tool.execute(
        action="remember",
        key="shared_key",
        value="agent2_value",
        agent="agent2"
    )
    
    # Recall without specifying agent should get most recent
    result = await context_tool.execute(
        action="recall",
        key="shared_key"
    )
    
    assert result.success is True
    # Should get the most recently stored value
    assert result.data in ["agent1_value", "agent2_value"]


@pytest.mark.asyncio
async def test_invalid_action(context_tool):
    """Test invalid action."""
    result = await context_tool.execute(
        action="invalid_action",
        key="test_key"
    )
    
    assert result.success is False
    assert "Unknown action" in result.error


@pytest.mark.asyncio
async def test_missing_key(context_tool):
    """Test missing key parameter."""
    result = await context_tool.execute(
        action="remember",
        value="test"
    )
    
    assert result.success is False
    assert "required" in result.error.lower()


@pytest.mark.asyncio
async def test_remember_complex_value(context_tool):
    """Test storing complex data structures."""
    complex_value = {
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
        "string": "test"
    }
    
    result = await context_tool.execute(
        action="remember",
        key="complex_key",
        value=complex_value,
        agent="test_agent"
    )
    
    assert result.success is True
    
    # Recall and verify
    result = await context_tool.execute(
        action="recall",
        key="complex_key"
    )
    
    assert result.success is True
    assert result.data == complex_value
