"""Tests for tool bridge layer."""

from typing import Any
import pytest
from aegis.core.tool_bridge import create_pydantic_tool, create_toolset_from_registry
from aegis.tools.base_tool import Tool, ToolResult
from aegis.tools.registry import ToolRegistry


class MockTool(Tool):
    """Mock tool for testing."""
    
    @property
    def name(self) -> str:
        return "mock_tool"
    
    @property
    def description(self) -> str:
        return "A mock tool for testing"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "test_param": {"type": "string"}
            },
            "required": ["test_param"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute mock tool."""
        test_param = kwargs.get("test_param", "")
        
        if test_param == "fail":
            return ToolResult(
                success=False,
                error="Mock error"
            )
        
        return ToolResult(
            success=True,
            data={"result": f"Processed: {test_param}"}
        )


@pytest.mark.asyncio
async def test_create_pydantic_tool_success():
    """Test successful tool conversion and execution."""
    mock_tool = MockTool()
    pydantic_tool = create_pydantic_tool(mock_tool)
    
    # Check function attributes
    assert pydantic_tool.__name__ == "mock_tool"
    assert pydantic_tool.__doc__ == "A mock tool for testing"
    
    # Test successful execution
    result = await pydantic_tool(test_param="hello")
    assert result["success"] is True
    assert result["data"]["result"] == "Processed: hello"


@pytest.mark.asyncio
async def test_create_pydantic_tool_failure():
    """Test tool conversion with failure case."""
    mock_tool = MockTool()
    pydantic_tool = create_pydantic_tool(mock_tool)
    
    # Test failed execution
    result = await pydantic_tool(test_param="fail")
    assert result["success"] is False
    assert result["error"] == "Mock error"


@pytest.mark.asyncio
async def test_create_toolset_from_registry():
    """Test creating toolset from registry."""
    # Create a mock registry
    registry = ToolRegistry()
    mock_tool = MockTool()
    registry.register_tool(mock_tool)
    
    # Create toolset
    toolset = create_toolset_from_registry(registry)
    
    # Should have one tool
    assert len(toolset) >= 1
    
    # Find our mock tool
    mock_pydantic_tool = None
    for tool in toolset:
        if tool.__name__ == "mock_tool":
            mock_pydantic_tool = tool
            break
    
    assert mock_pydantic_tool is not None
    
    # Test execution
    result = await mock_pydantic_tool(test_param="test")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_create_toolset_empty_registry():
    """Test creating toolset from empty registry."""
    registry = ToolRegistry()
    toolset = create_toolset_from_registry(registry)
    
    # Should return empty list or list with only default tools
    assert isinstance(toolset, list)
