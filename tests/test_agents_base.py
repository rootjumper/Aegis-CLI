"""Tests for base agent contract."""

import pytest
from aegis.agents.base import AgentTask, ToolCall, AgentResponse


def test_agent_task_creation() -> None:
    """Test creating an AgentTask."""
    task = AgentTask(
        id="test-123",
        type="code",
        payload={"description": "Test task"}
    )
    
    assert task.id == "test-123"
    assert task.type == "code"
    assert task.payload["description"] == "Test task"
    assert task.dependencies == []
    assert task.max_retries == 3


def test_tool_call_creation() -> None:
    """Test creating a ToolCall."""
    tool_call = ToolCall(
        tool_name="filesystem",
        parameters={"action": "read_file", "path": "test.py"}
    )
    
    assert tool_call.tool_name == "filesystem"
    assert tool_call.parameters["action"] == "read_file"
    assert tool_call.success is True
    assert tool_call.error is None


def test_agent_response_creation() -> None:
    """Test creating an AgentResponse."""
    response = AgentResponse(
        status="SUCCESS",
        data={"result": "test"},
        reasoning_trace="Test reasoning"
    )
    
    assert response.status == "SUCCESS"
    assert response.data["result"] == "test"
    assert response.reasoning_trace == "Test reasoning"
    assert response.tool_calls == []
    assert response.errors == []


def test_agent_task_with_dependencies() -> None:
    """Test creating an AgentTask with dependencies."""
    task = AgentTask(
        id="test-123",
        type="test",
        payload={"description": "Test task"},
        dependencies=["task-1", "task-2"]
    )
    
    assert len(task.dependencies) == 2
    assert "task-1" in task.dependencies
