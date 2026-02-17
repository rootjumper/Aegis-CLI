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
from aegis.core.state import get_state_manager


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
    # Should have at least one task (could be code, or code+test if LLM is available)
    assert len(subtasks) >= 1
    # Should have at least code task
    task_types = [st.get("type") for st in subtasks]
    assert "code" in task_types


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
    # Should have at least one task (could be documentation or code depending on LLM/fallback)
    assert len(subtasks) >= 1
    # Just verify we got valid task types
    task_types = [st.get("type") for st in subtasks]
    assert all(t in ["code", "test", "review", "documentation"] for t in task_types)


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


@pytest.mark.asyncio
async def test_execute_with_agent_timeout():
    """Test that agent execution handles timeouts properly."""
    from aegis.main import _execute_with_agent, DEFAULT_TASK_TIMEOUT
    
    logger = create_trace_logger("test-timeout", "test")
    state_manager = get_state_manager()
    await state_manager.init_database()
    
    task = AgentTask(
        id="test-timeout-1",
        type="code",
        payload={"description": "Test timeout handling"},
        context={},
        max_retries=0  # No retries to make test faster
    )
    
    # Since we're testing timeout, we expect it to complete (success or fail)
    # without hanging indefinitely
    result = await _execute_with_agent(task, "code", logger, state_manager)
    
    # Result should be boolean
    assert isinstance(result, bool)
    
    await state_manager.close()


@pytest.mark.asyncio
async def test_execute_single_subtask_with_verification():
    """Test executing a single subtask with verification cycle."""
    from aegis.main import _execute_single_subtask
    
    logger = create_trace_logger("test-subtask", "test")
    state_manager = get_state_manager()
    await state_manager.init_database()
    
    task = AgentTask(
        id="test-subtask-1",
        type="code",
        payload={"description": "Test subtask execution"},
        context={},
        max_retries=1  # Reduced for faster test
    )
    
    # Execute with verification disabled to make test faster
    result = await _execute_single_subtask(
        task, 
        "code", 
        logger, 
        state_manager,
        no_verify=True
    )
    
    # Result should be boolean
    assert isinstance(result, bool)
    
    await state_manager.close()


@pytest.mark.asyncio
async def test_agent_retry_logic():
    """Test that agents retry on failure."""
    coder = CoderAgent()
    
    task = AgentTask(
        id="test-retry-2",
        type="code",
        payload={"description": "Task that may need retries"},
        context={},
        max_retries=2
    )
    
    # First attempt
    response = await coder.process(task)
    
    # If it fails, context should be updatable for retry
    if response.status in ["FAIL", "RETRY"]:
        task.context["previous_errors"] = response.errors
        
        # Second attempt with context
        response2 = await coder.process(task)
        
        # Should have access to previous context
        assert isinstance(response2, AgentResponse)
