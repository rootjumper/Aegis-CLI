"""Tests for Testing tool."""

import pytest
from aegis.tools.testing import TestingTool


@pytest.fixture
def testing_tool():
    """Create a TestingTool instance."""
    return TestingTool()


def test_testing_tool_creation(testing_tool):
    """Test creating a TestingTool."""
    assert testing_tool.name == "testing"
    assert "test" in testing_tool.description.lower()


def test_testing_tool_schema(testing_tool):
    """Test TestingTool parameter schema."""
    schema = testing_tool.parameters_schema
    
    assert "properties" in schema
    assert "action" in schema["properties"]
    assert schema["required"] == ["action"]
    assert "run_tests" in schema["properties"]["action"]["enum"]


@pytest.mark.asyncio
async def test_list_tests(testing_tool):
    """Test listing tests."""
    result = await testing_tool.execute(
        action="list_tests",
        path="tests/"
    )
    
    # Should succeed even if path doesn't exist or has issues
    assert result.data is not None


@pytest.mark.asyncio
async def test_validate_tests(testing_tool):
    """Test validating tests."""
    result = await testing_tool.execute(
        action="validate_tests",
        path="tests/"
    )
    
    assert result.data is not None
    assert "test_files" in result.data
    assert "issues" in result.data


@pytest.mark.asyncio
async def test_invalid_action(testing_tool):
    """Test invalid action."""
    result = await testing_tool.execute(
        action="invalid_action"
    )
    
    assert result.success is False
    assert "Unknown action" in result.error


@pytest.mark.asyncio
async def test_parse_pytest_output(testing_tool):
    """Test parsing pytest output."""
    output = "5 passed, 2 failed, 1 skipped"
    result = testing_tool._parse_pytest_output(output)
    
    assert result["passed"] == 5
    assert result["failed"] == 2
    assert result["skipped"] == 1


@pytest.mark.asyncio
async def test_parse_coverage(testing_tool):
    """Test parsing coverage output."""
    output = "TOTAL      100     10     90%"
    result = testing_tool._parse_coverage(output)
    
    assert result == 90.0


@pytest.mark.asyncio
async def test_nonexistent_test_path(testing_tool):
    """Test with non-existent test path."""
    result = await testing_tool.execute(
        action="validate_tests",
        path="/nonexistent/path/"
    )
    
    assert result.success is False
    assert "not found" in result.error.lower()
