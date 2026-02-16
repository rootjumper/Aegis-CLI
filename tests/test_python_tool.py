"""Tests for Python tool."""

import os
import tempfile
import pytest
from pathlib import Path

from aegis.tools.python import PythonTool


@pytest.fixture
def python_tool():
    """Create a PythonTool instance."""
    return PythonTool()


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
import os
from pathlib import Path

class TestClass:
    '''Test class docstring.'''
    
    def __init__(self):
        pass
    
    def test_method(self):
        '''Test method docstring.'''
        return "test"

def test_function(arg1, arg2):
    '''Test function docstring.'''
    return arg1 + arg2

async def async_function():
    '''Async function.'''
    pass
""")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    try:
        os.unlink(temp_path)
    except:
        pass


def test_python_tool_creation(python_tool):
    """Test creating a PythonTool."""
    assert python_tool.name == "python"
    assert "python" in python_tool.description.lower()


def test_python_tool_schema(python_tool):
    """Test PythonTool parameter schema."""
    schema = python_tool.parameters_schema
    
    assert "properties" in schema
    assert "action" in schema["properties"]
    assert "path" in schema["required"]
    assert "analyze_imports" in schema["properties"]["action"]["enum"]


@pytest.mark.asyncio
async def test_analyze_imports(python_tool, temp_python_file):
    """Test analyzing imports."""
    result = await python_tool.execute(
        action="analyze_imports",
        path=temp_python_file
    )
    
    assert result.success is True
    assert "imports" in result.data
    assert "total" in result.data


@pytest.mark.asyncio
async def test_parse_syntax_valid(python_tool, temp_python_file):
    """Test parsing valid Python syntax."""
    result = await python_tool.execute(
        action="parse_syntax",
        path=temp_python_file
    )
    
    assert result.success is True
    assert result.data["valid"] is True


@pytest.mark.asyncio
async def test_parse_syntax_invalid(python_tool):
    """Test parsing invalid Python syntax."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("def invalid syntax here\n")
        temp_path = f.name
    
    try:
        result = await python_tool.execute(
            action="parse_syntax",
            path=temp_path
        )
        
        assert result.success is False
        assert "Syntax error" in result.error
    finally:
        os.unlink(temp_path)


@pytest.mark.asyncio
async def test_get_functions(python_tool, temp_python_file):
    """Test extracting functions from Python file."""
    result = await python_tool.execute(
        action="get_functions",
        path=temp_python_file
    )
    
    assert result.success is True
    assert "functions" in result.data
    assert result.data["count"] >= 3  # test_function, async_function, and __init__/test_method
    
    # Check function details
    function_names = [f["name"] for f in result.data["functions"]]
    assert "test_function" in function_names
    assert "async_function" in function_names


@pytest.mark.asyncio
async def test_get_classes(python_tool, temp_python_file):
    """Test extracting classes from Python file."""
    result = await python_tool.execute(
        action="get_classes",
        path=temp_python_file
    )
    
    assert result.success is True
    assert "classes" in result.data
    assert result.data["count"] >= 1
    
    # Check class details
    test_class = result.data["classes"][0]
    assert test_class["name"] == "TestClass"
    assert "test_method" in test_class["methods"]
    assert test_class["docstring"] is not None


@pytest.mark.asyncio
async def test_invalid_action(python_tool):
    """Test invalid action."""
    result = await python_tool.execute(
        action="invalid_action",
        path="/tmp/test.py"
    )
    
    assert result.success is False
    assert "Unknown action" in result.error


@pytest.mark.asyncio
async def test_nonexistent_file(python_tool):
    """Test analyzing non-existent file."""
    result = await python_tool.execute(
        action="analyze_imports",
        path="/nonexistent/file.py"
    )
    
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_missing_path(python_tool):
    """Test missing path parameter."""
    result = await python_tool.execute(
        action="analyze_imports",
        path=""
    )
    
    assert result.success is False
    assert "required" in result.error.lower()
