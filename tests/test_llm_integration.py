"""Integration tests for LLM-enabled agents.

These tests verify that agents have the proper structure and interfaces.
Full LLM integration testing requires actual LLM calls or complex mocking.
"""

import pytest
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.coder import CoderAgent
from aegis.agents.tester import TesterAgent
from aegis.agents.critic import CriticAgent
from aegis.agents.janitor import JanitorAgent
from aegis.agents.base import AgentTask
from aegis.core.tool_bridge import create_toolset_from_registry
from aegis.tools.registry import get_registry


def test_tool_bridge_creates_toolset():
    """Test that tool bridge can create toolset from registry."""
    registry = get_registry()
    toolset = create_toolset_from_registry(registry)
    
    # Should have tools registered
    assert isinstance(toolset, list)
    assert len(toolset) > 0
    
    # Each item should be callable
    for tool in toolset:
        assert callable(tool)


def test_agents_have_models():
    """Test that agents can be instantiated with models."""
    from aegis.core.llm_config import get_default_model
    
    try:
        model = get_default_model()
        
        # Create agents with model
        orchestrator = OrchestratorAgent(model=model)
        coder = CoderAgent(model=model)
        tester = TesterAgent(model=model)
        critic = CriticAgent(model=model)
        janitor = JanitorAgent(model=model)
        
        # Verify they have the model
        assert orchestrator.get_model() is not None
        assert coder.get_model() is not None
        assert tester.get_model() is not None
        assert critic.get_model() is not None
        assert janitor.get_model() is not None
        
    except ValueError as e:
        # If no LLM is configured, that's expected in test environment
        if "No LLM provider configured" in str(e):
            pytest.skip("No LLM provider configured for testing")
        raise


def test_agents_have_system_prompts():
    """Test that all agents have system prompts."""
    orchestrator = OrchestratorAgent()
    coder = CoderAgent()
    tester = TesterAgent()
    critic = CriticAgent()
    janitor = JanitorAgent()
    
    # All agents should have non-empty system prompts
    assert len(orchestrator.get_system_prompt()) > 0
    assert len(coder.get_system_prompt()) > 0
    assert len(tester.get_system_prompt()) > 0
    assert len(critic.get_system_prompt()) > 0
    assert len(janitor.get_system_prompt()) > 0
    
    # System prompts should describe the agent's role
    assert "orchestrator" in orchestrator.get_system_prompt().lower()
    assert "coder" in coder.get_system_prompt().lower() or "code" in coder.get_system_prompt().lower()
    assert "test" in tester.get_system_prompt().lower()
    assert "review" in critic.get_system_prompt().lower() or "critic" in critic.get_system_prompt().lower()
    assert "documentation" in janitor.get_system_prompt().lower() or "janitor" in janitor.get_system_prompt().lower()


def test_agents_have_required_tools():
    """Test that all agents specify their required tools."""
    orchestrator = OrchestratorAgent()
    coder = CoderAgent()
    tester = TesterAgent()
    critic = CriticAgent()
    janitor = JanitorAgent()
    
    # All agents should return a list of tool names
    assert isinstance(orchestrator.get_required_tools(), list)
    assert isinstance(coder.get_required_tools(), list)
    assert isinstance(tester.get_required_tools(), list)
    assert isinstance(critic.get_required_tools(), list)
    assert isinstance(janitor.get_required_tools(), list)
    
    # Coder should require filesystem
    assert "filesystem" in coder.get_required_tools()
    
    # Tester should require filesystem and shell
    assert "filesystem" in tester.get_required_tools()
    assert "shell" in tester.get_required_tools()


@pytest.mark.asyncio
async def test_orchestrator_fallback_decomposition():
    """Test orchestrator fallback decomposition when LLM fails."""
    orchestrator = OrchestratorAgent()
    
    # Even without LLM, should fall back to keyword matching
    tasks = await orchestrator.decompose_prompt("Create a hello world function")
    
    # Should return at least one task
    assert len(tasks) >= 1
    assert tasks[0]["type"] in ["code", "test", "review", "documentation"]
    assert "description" in tasks[0]
    assert "priority" in tasks[0]


@pytest.mark.asyncio
async def test_agent_task_validation():
    """Test that agents validate their inputs correctly."""
    orchestrator = OrchestratorAgent()
    coder = CoderAgent()
    tester = TesterAgent()
    critic = CriticAgent()
    janitor = JanitorAgent()
    
    # Valid tasks
    valid_orchestrator_task = AgentTask(
        id="test-1",
        type="orchestrate",
        payload={"prompt": "Create a function"}
    )
    
    valid_coder_task = AgentTask(
        id="test-2",
        type="code",
        payload={"description": "Create a function"}
    )
    
    valid_tester_task = AgentTask(
        id="test-3",
        type="test",
        payload={"code": "def hello(): pass"}
    )
    
    valid_critic_task = AgentTask(
        id="test-4",
        type="review",
        payload={"code": "def hello(): pass"}
    )
    
    valid_janitor_task = AgentTask(
        id="test-5",
        type="documentation",
        payload={"doc_type": "readme"}
    )
    
    # Validation should pass
    assert await orchestrator.validate_input(valid_orchestrator_task)
    assert await coder.validate_input(valid_coder_task)
    assert await tester.validate_input(valid_tester_task)
    assert await critic.validate_input(valid_critic_task)
    assert await janitor.validate_input(valid_janitor_task)
    
    # Invalid tasks (missing required fields)
    invalid_orchestrator_task = AgentTask(
        id="test-6",
        type="orchestrate",
        payload={}  # Missing prompt
    )
    
    invalid_coder_task = AgentTask(
        id="test-7",
        type="code",
        payload={}  # Missing description
    )
    
    invalid_tester_task = AgentTask(
        id="test-8",
        type="test",
        payload={}  # Missing code/file_path
    )
    
    invalid_critic_task = AgentTask(
        id="test-9",
        type="review",
        payload={}  # Missing code
    )
    
    invalid_janitor_task = AgentTask(
        id="test-10",
        type="documentation",
        payload={}  # Missing doc_type
    )
    
    # Validation should fail
    assert not await orchestrator.validate_input(invalid_orchestrator_task)
    assert not await coder.validate_input(invalid_coder_task)
    assert not await tester.validate_input(invalid_tester_task)
    assert not await critic.validate_input(invalid_critic_task)
    assert not await janitor.validate_input(invalid_janitor_task)
