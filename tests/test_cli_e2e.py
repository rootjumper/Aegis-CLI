"""End-to-end CLI tests."""

import subprocess
import pytest


def test_cli_help():
    """Test CLI help command."""
    result = subprocess.run(
        ["aegis", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Aegis-CLI" in result.stdout
    assert "Commands" in result.stdout


def test_cli_tools_command():
    """Test listing tools."""
    result = subprocess.run(
        ["aegis", "tools"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "filesystem" in result.stdout
    assert "shell" in result.stdout
    assert "context" in result.stdout
    assert "git" in result.stdout
    assert "testing" in result.stdout
    assert "python" in result.stdout


def test_cli_agents_command():
    """Test listing agents."""
    result = subprocess.run(
        ["aegis", "agents"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Orchestrator" in result.stdout
    assert "Coder" in result.stdout
    assert "Critic" in result.stdout
    assert "Tester" in result.stdout
    assert "Janitor" in result.stdout


def test_cli_doctor_command():
    """Test doctor health check command."""
    result = subprocess.run(
        ["aegis", "doctor"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Health Check" in result.stdout
    assert "Python Version" in result.stdout
    assert "Available Tools" in result.stdout


def test_cli_validate_command():
    """Test validate configuration command."""
    result = subprocess.run(
        ["aegis", "validate"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Configuration Validation" in result.stdout
    assert "tools available" in result.stdout


def test_cli_history_command():
    """Test history command (should work even with no history)."""
    result = subprocess.run(
        ["aegis", "history"],
        capture_output=True,
        text=True
    )
    
    # Should succeed even with no history
    assert result.returncode == 0


def test_cli_status_command():
    """Test status command (should work even with no tasks)."""
    result = subprocess.run(
        ["aegis", "status"],
        capture_output=True,
        text=True
    )
    
    # Should succeed even with no tasks
    assert result.returncode == 0


def test_cli_invalid_command():
    """Test invalid command."""
    result = subprocess.run(
        ["aegis", "invalid_command"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode != 0


def test_cli_run_help():
    """Test run command help."""
    result = subprocess.run(
        ["aegis", "run", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "prompt" in result.stdout.lower()
    assert "verbose" in result.stdout.lower()
