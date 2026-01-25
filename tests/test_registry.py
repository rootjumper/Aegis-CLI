"""Tests for tool registry."""

import pytest
from aegis.tools.registry import get_registry, ToolRegistry


def test_get_registry() -> None:
    """Test getting global registry instance."""
    registry1 = get_registry()
    registry2 = get_registry()
    
    # Should return same instance
    assert registry1 is registry2


def test_list_available_tools() -> None:
    """Test listing available tools."""
    registry = get_registry()
    tools = registry.list_available_tools()
    
    assert isinstance(tools, list)
    assert "filesystem" in tools
    assert "shell" in tools
    assert "context" in tools


def test_get_tool() -> None:
    """Test getting a tool by name."""
    registry = get_registry()
    
    tool = registry.get_tool("filesystem")
    assert tool is not None
    assert tool.name == "filesystem"
    
    # Non-existent tool
    tool = registry.get_tool("nonexistent")
    assert tool is None


def test_get_all_tools() -> None:
    """Test getting all tools."""
    registry = get_registry()
    all_tools = registry.get_all_tools()
    
    assert isinstance(all_tools, dict)
    assert "filesystem" in all_tools
    assert len(all_tools) >= 3  # At least filesystem, shell, context
