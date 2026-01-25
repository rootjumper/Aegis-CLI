"""Tests for tool implementations."""

import pytest
from aegis.tools.filesystem import FileSystemTool
from aegis.tools.shell import SafeShell
from aegis.tools.context import ContextTool


def test_filesystem_tool_creation() -> None:
    """Test creating a FileSystemTool."""
    tool = FileSystemTool()
    
    assert tool.name == "filesystem"
    assert "read" in tool.description.lower()


def test_filesystem_tool_schema() -> None:
    """Test FileSystemTool parameter schema."""
    tool = FileSystemTool()
    schema = tool.parameters_schema
    
    assert "properties" in schema
    assert "action" in schema["properties"]
    assert schema["required"] == ["action"]


def test_safe_shell_creation() -> None:
    """Test creating a SafeShell tool."""
    tool = SafeShell()
    
    assert tool.name == "shell"
    assert "command" in tool.description.lower()


def test_safe_shell_whitelisted_commands() -> None:
    """Test SafeShell command whitelist."""
    assert "pytest" in SafeShell.SAFE_COMMANDS
    assert "git" in SafeShell.SAFE_COMMANDS
    assert "pip" in SafeShell.SAFE_COMMANDS
    # Dangerous commands should not be in whitelist
    assert "rm" not in SafeShell.SAFE_COMMANDS
    assert "sudo" not in SafeShell.SAFE_COMMANDS


def test_context_tool_creation() -> None:
    """Test creating a ContextTool."""
    tool = ContextTool()
    
    assert tool.name == "context"
    assert "memory" in tool.description.lower()


def test_tool_validation() -> None:
    """Test tool parameter validation."""
    tool = FileSystemTool()
    
    # Valid parameters
    assert tool.validate_params({"action": "read_file", "path": "test.py"}) is True
    
    # Missing required parameter
    assert tool.validate_params({}) is False
