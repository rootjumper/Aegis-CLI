"""Tests for LLM Logger functionality."""

import tempfile
import os
from pathlib import Path

from aegis.core.llm_logger import LLMLogger
from aegis.agents.coder import CoderAgent
from aegis.agents.tester import TesterAgent
from aegis.agents.orchestrator import OrchestratorAgent


def test_llm_logger_initialization():
    """Test LLMLogger can be initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        assert logger is not None
        assert logger.log_dir == Path(tmpdir)
        assert logger.verbose is False
        assert logger.interaction_count == 0


def test_llm_logger_prompt_logging():
    """Test logging prompts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        interaction_id = logger.log_prompt(
            agent_name="TestAgent",
            prompt="Test prompt",
            model="test-model",
            system_prompt="System prompt",
            tools=["tool1", "tool2"]
        )
        
        assert interaction_id == 1
        assert logger.interaction_count == 1
        assert logger.session_log.exists()
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            assert "PROMPT" in content
            assert "TestAgent" in content
            assert "Test prompt" in content


def test_llm_logger_response_logging():
    """Test logging responses."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        interaction_id = logger.log_prompt(
            agent_name="TestAgent",
            prompt="Test prompt",
            model="test-model"
        )
        
        logger.log_response(
            interaction_id=interaction_id,
            agent_name="TestAgent",
            response="Mock response",
            raw_response="Raw response text",
            extracted_content="Extracted content",
            finish_reason="stop"
        )
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            assert "RESPONSE" in content
            assert "Raw response text" in content
            assert "Extracted content" in content


def test_llm_logger_file_operation_logging():
    """Test logging file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        logger.log_file_operation(
            agent_name="TestAgent",
            operation="write_file",
            file_path="/tmp/test.py",
            success=True,
            content_preview='print("hello")'
        )
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            assert "FILE OPERATION" in content
            assert "write_file" in content
            assert "/tmp/test.py" in content


def test_llm_logger_tool_call_logging():
    """Test logging tool calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        logger.log_tool_call(
            agent_name="TestAgent",
            tool_name="filesystem",
            parameters={"action": "read_file", "path": "/tmp/test.py"},
            result="File content",
            success=True
        )
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            assert "TOOL CALL" in content
            assert "filesystem" in content


def test_llm_logger_session_summary():
    """Test getting session summary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        logger.log_prompt(
            agent_name="TestAgent",
            prompt="Test prompt",
            model="test-model"
        )
        
        summary = logger.get_session_summary()
        
        assert "session_log" in summary
        assert "interactions" in summary
        assert summary["interactions"] == 1
        assert summary["log_size"] > 0


def test_coder_agent_has_llm_logger():
    """Test CoderAgent has LLM logger."""
    agent = CoderAgent(verbose=True)
    
    assert hasattr(agent, "llm_logger")
    assert agent.llm_logger.verbose is True


def test_tester_agent_has_llm_logger():
    """Test TesterAgent has LLM logger."""
    agent = TesterAgent(verbose=True)
    
    assert hasattr(agent, "llm_logger")
    assert agent.llm_logger.verbose is True


def test_orchestrator_agent_has_llm_logger():
    """Test OrchestratorAgent has LLM logger."""
    agent = OrchestratorAgent(verbose=True)
    
    assert hasattr(agent, "llm_logger")
    assert agent.llm_logger.verbose is True


def test_workspace_name_generation():
    """Test smart workspace name generation."""
    orchestrator = OrchestratorAgent()
    
    test_cases = [
        ("Create a Product model", "product_model"),
        ("Build REST API for users", "rest_api_users"),
        ("HTML calculator app", "html_calculator_app"),
        ("Implement authentication system", "authentication_system"),
        ("make a simple todo list", "simple_todo_list"),
    ]
    
    for description, expected_pattern in test_cases:
        result = orchestrator._generate_workspace_name(description)
        # Check if result contains expected keywords (first two words)
        expected_words = expected_pattern.split('_')[:2]
        assert all(word in result for word in expected_words), \
            f"Expected '{expected_pattern}' pattern in '{result}'"


def test_workspace_name_removes_filler_words():
    """Test that filler words are removed from workspace names."""
    orchestrator = OrchestratorAgent()
    
    result = orchestrator._generate_workspace_name("Please create a user model for me")
    assert "please" not in result
    assert "create" not in result
    assert "for" not in result
    assert "me" not in result
    assert "user" in result
    assert "model" in result


def test_workspace_name_fallback():
    """Test workspace name fallback for empty input."""
    orchestrator = OrchestratorAgent()
    
    result = orchestrator._generate_workspace_name("")
    assert result.startswith("project_")
    assert len(result) > len("project_")


def test_workspace_name_length_limit():
    """Test workspace name length is limited."""
    orchestrator = OrchestratorAgent()
    
    long_description = "create a " + " ".join([f"word{i}" for i in range(20)])
    result = orchestrator._generate_workspace_name(long_description)
    
    assert len(result) <= 50


def test_workspace_name_sanitization():
    """Test workspace name sanitization."""
    orchestrator = OrchestratorAgent()
    
    result = orchestrator._generate_workspace_name("Create a @#$% model with special! chars")
    # Should only contain alphanumeric and underscores
    assert all(c.isalnum() or c == '_' for c in result)
    # Should not have consecutive underscores
    assert '__' not in result
    # Should not start or end with underscore
    assert not result.startswith('_')
    assert not result.endswith('_')


def test_extract_tool_info_with_string():
    """Test extracting tool info from string."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        tools = ["tool1", "tool2"]
        tool_info = logger._extract_tool_info(tools)
        
        assert len(tool_info) == 2
        assert tool_info[0]['name'] == "tool1"
        assert tool_info[0]['type'] == "string"
        assert tool_info[1]['name'] == "tool2"


def test_extract_tool_info_with_tool_object():
    """Test extracting tool info from actual tool object."""
    from aegis.tools.filesystem import FileSystemTool
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        fs_tool = FileSystemTool()
        tool_info = logger._extract_tool_info([fs_tool])
        
        assert len(tool_info) == 1
        assert tool_info[0]['name'] == "filesystem"
        assert 'description' in tool_info[0]
        assert 'parameters' in tool_info[0]
        assert isinstance(tool_info[0]['parameters'], dict)


def test_extract_tool_info_with_callable():
    """Test extracting tool info from callable function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        def test_function(arg1: str, arg2: int) -> str:
            """Test function description."""
            return "result"
        
        test_function.__name__ = "test_tool"
        tool_info = logger._extract_tool_info([test_function])
        
        assert len(tool_info) == 1
        assert tool_info[0]['name'] == "test_tool"
        assert 'signature' in tool_info[0]
        assert 'arg1' in tool_info[0]['signature']
        assert 'arg2' in tool_info[0]['signature']


def test_log_prompt_with_enhanced_tool_info():
    """Test that log_prompt logs comprehensive tool information."""
    from aegis.tools.filesystem import FileSystemTool
    
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        fs_tool = FileSystemTool()
        
        interaction_id = logger.log_prompt(
            agent_name="TestAgent",
            prompt="Test prompt",
            model="test-model",
            tools=[fs_tool]
        )
        
        assert interaction_id == 1
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            # Should contain tool name
            assert "filesystem" in content
            # Should contain tool details section
            assert "TOOLS (1)" in content
            # Should contain description
            assert "Description:" in content
            # Should contain parameters
            assert "Parameters:" in content


def test_log_prompt_with_no_tools():
    """Test that log_prompt handles no tools gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        interaction_id = logger.log_prompt(
            agent_name="TestAgent",
            prompt="Test prompt",
            model="test-model",
            tools=None
        )
        
        assert interaction_id == 1
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            # Should indicate text-based mode
            assert "TOOLS: None (text-based mode)" in content


def test_log_prompt_with_empty_tools_list():
    """Test that log_prompt handles empty tools list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = LLMLogger(log_dir=tmpdir, verbose=False)
        
        interaction_id = logger.log_prompt(
            agent_name="TestAgent",
            prompt="Test prompt",
            model="test-model",
            tools=[]
        )
        
        assert interaction_id == 1
        
        # Check log file content
        with open(logger.session_log, 'r') as f:
            content = f.read()
            # Should indicate text-based mode
            assert "TOOLS: None (text-based mode)" in content
