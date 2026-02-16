"""Integration tests for shell tool."""

import pytest
from aegis.tools.shell import SafeShell


@pytest.fixture
def shell_tool():
    """Create a SafeShell instance."""
    return SafeShell()


def test_shell_tool_creation(shell_tool):
    """Test creating a SafeShell tool."""
    assert shell_tool.name == "shell"
    assert "command" in shell_tool.description.lower()


def test_shell_tool_schema(shell_tool):
    """Test SafeShell parameter schema."""
    schema = shell_tool.parameters_schema
    
    assert "properties" in schema
    assert "command" in schema["properties"]
    assert schema["required"] == ["command"]


def test_shell_safe_commands(shell_tool):
    """Test that expected commands are whitelisted."""
    assert "git" in SafeShell.SAFE_COMMANDS
    assert "pytest" in SafeShell.SAFE_COMMANDS
    assert "python" in SafeShell.SAFE_COMMANDS
    assert "mypy" in SafeShell.SAFE_COMMANDS
    assert "pylint" in SafeShell.SAFE_COMMANDS
    
    # New commands added
    assert "black" in SafeShell.SAFE_COMMANDS
    assert "ruff" in SafeShell.SAFE_COMMANDS
    assert "npm" in SafeShell.SAFE_COMMANDS
    assert "docker" in SafeShell.SAFE_COMMANDS


def test_shell_dangerous_commands_not_whitelisted():
    """Test that dangerous commands are not whitelisted."""
    assert "rm" not in SafeShell.SAFE_COMMANDS
    assert "sudo" not in SafeShell.SAFE_COMMANDS
    assert "chmod" not in SafeShell.SAFE_COMMANDS
    assert "chown" not in SafeShell.SAFE_COMMANDS
    assert "dd" not in SafeShell.SAFE_COMMANDS


@pytest.mark.asyncio
async def test_shell_execute_echo(shell_tool):
    """Test executing a simple echo command."""
    result = await shell_tool.execute(
        command=["echo", "Hello World"],
        require_confirmation=False
    )
    
    assert result.success is True
    assert result.data is not None
    assert result.data["returncode"] == 0


@pytest.mark.asyncio
async def test_shell_execute_pwd(shell_tool):
    """Test executing pwd command."""
    result = await shell_tool.execute(
        command=["pwd"],
        require_confirmation=False
    )
    
    assert result.success is True
    assert result.data["returncode"] == 0
    assert result.data["stdout"] is not None


@pytest.mark.asyncio
async def test_shell_non_whitelisted_command(shell_tool):
    """Test that non-whitelisted commands are rejected."""
    result = await shell_tool.execute(
        command=["rm", "-rf", "/"],
        require_confirmation=False
    )
    
    assert result.success is False
    assert "not whitelisted" in result.error


@pytest.mark.asyncio
async def test_shell_empty_command(shell_tool):
    """Test that empty command is rejected."""
    result = await shell_tool.execute(
        command=[],
        require_confirmation=False
    )
    
    assert result.success is False
    assert "required" in result.error.lower()


@pytest.mark.asyncio
async def test_shell_command_timeout():
    """Test command timeout handling."""
    shell_tool = SafeShell()
    
    # Test timeout functionality with a long-running command
    # Using a very short timeout (1 second) to fail fast
    result = await shell_tool.execute(
        command=["python", "-c", "import time; time.sleep(100)"],
        require_confirmation=False,
        timeout=1  # 1 second timeout
    )
    
    # Command should timeout with success=False
    # Note: We check both error message and data because timeout handling
    # may return error message OR error data depending on how subprocess fails
    assert result.success is False
    is_timeout_error = "timed out" in result.error.lower() if result.error else False
    has_error_data = result.data is not None
    assert is_timeout_error or has_error_data, \
        "Command should timeout with error message or error data"
