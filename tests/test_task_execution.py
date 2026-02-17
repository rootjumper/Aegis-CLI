"""Tests for task execution and agent orchestration."""

import asyncio
import pytest
from aegis.agents.base import AgentTask, AgentResponse
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.coder import CoderAgent
from aegis.agents.tester import TesterAgent
from aegis.agents.critic import CriticAgent
from aegis.core.verification import VerificationCycle
from aegis.core.logging import create_trace_logger


@pytest.mark.asyncio
async def test_orchestrator_decomposes_code_task():
    """Test that orchestrator decomposes a code task."""
    orchestrator = OrchestratorAgent()
    
    task = AgentTask(
        id="test-task-1",
        type="user_prompt",
        payload={"prompt": "create a function to calculate fibonacci numbers"},
        context={}
    )
    
    response = await orchestrator.process(task)
    
    assert response.status == "SUCCESS"
    assert "subtasks" in response.data
    subtasks = response.data["subtasks"]
    assert len(subtasks) > 0
    assert any(st.get("type") == "code" for st in subtasks)


@pytest.mark.asyncio
async def test_orchestrator_decomposes_test_task():
    """Test that orchestrator includes test tasks when appropriate."""
    orchestrator = OrchestratorAgent()
    
    task = AgentTask(
        id="test-task-2",
        type="user_prompt",
        payload={"prompt": "create and test a sorting function"},
        context={}
    )
    
    response = await orchestrator.process(task)
    
    assert response.status == "SUCCESS"
    subtasks = response.data["subtasks"]
    assert len(subtasks) >= 2
    # Should have both code and test tasks
    task_types = [st.get("type") for st in subtasks]
    assert "code" in task_types
    assert "test" in task_types


@pytest.mark.asyncio
async def test_orchestrator_decomposes_documentation_task():
    """Test that orchestrator includes documentation tasks."""
    orchestrator = OrchestratorAgent()
    
    task = AgentTask(
        id="test-task-3",
        type="user_prompt",
        payload={"prompt": "document the API endpoints"},
        context={}
    )
    
    response = await orchestrator.process(task)
    
    assert response.status == "SUCCESS"
    subtasks = response.data["subtasks"]
    assert any(st.get("type") == "documentation" for st in subtasks)


@pytest.mark.asyncio
async def test_coder_agent_processes_task():
    """Test that coder agent can process a task."""
    coder = CoderAgent()
    
    task = AgentTask(
        id="test-coder-1",
        type="code",
        payload={
            "description": "Create a simple add function",
            "file_path": "/tmp/test_add.py"
        },
        context={}
    )
    
    response = await coder.process(task)
    
    # Response should be either SUCCESS or FAIL, not PENDING
    assert response.status in ["SUCCESS", "FAIL"]
    assert response.reasoning_trace is not None


@pytest.mark.asyncio
async def test_verification_cycle_initializes():
    """Test that verification cycle can be initialized."""
    logger = create_trace_logger("test-verification", "test")
    
    coder = CoderAgent()
    tester = TesterAgent()
    critic = CriticAgent()
    
    verification = VerificationCycle(
        coder=coder,
        tester=tester,
        critic=critic,
        logger=logger
    )
    
    assert verification.coder is not None
    assert verification.tester is not None
    assert verification.critic is not None
    assert verification.logger is not None


@pytest.mark.asyncio
async def test_agent_response_has_correct_structure():
    """Test that agent responses have the correct structure."""
    coder = CoderAgent()
    
    task = AgentTask(
        id="test-response-1",
        type="code",
        payload={"description": "Test task"},
        context={}
    )
    
    response = await coder.process(task)
    
    # Verify response structure
    assert hasattr(response, "status")
    assert hasattr(response, "data")
    assert hasattr(response, "reasoning_trace")
    assert hasattr(response, "tool_calls")
    assert hasattr(response, "errors")
    
    # Verify types
    assert isinstance(response.status, str)
    assert isinstance(response.data, dict)
    assert isinstance(response.reasoning_trace, str)
    assert isinstance(response.tool_calls, list)
    assert isinstance(response.errors, list)


@pytest.mark.asyncio
async def test_agent_task_with_max_retries():
    """Test that agent tasks respect max_retries setting."""
    task = AgentTask(
        id="test-retry-1",
        type="code",
        payload={"description": "Test task"},
        context={},
        max_retries=2
    )
    
    assert task.max_retries == 2


@pytest.mark.asyncio
async def test_agent_task_with_context():
    """Test that agent tasks can carry context."""
    task = AgentTask(
        id="test-context-1",
        type="code",
        payload={"description": "Test task"},
        context={
            "previous_errors": ["Error 1", "Error 2"],
            "test_feedback": ["Test failed at line 10"]
        },
        max_retries=3
    )
    
    assert "previous_errors" in task.context
    assert "test_feedback" in task.context
    assert len(task.context["previous_errors"]) == 2
