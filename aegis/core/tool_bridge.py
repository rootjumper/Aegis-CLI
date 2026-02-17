"""Bridge layer to convert Aegis Tools to PydanticAI-compatible functions.

This module provides utilities to convert Aegis Tool instances into functions
that can be used as PydanticAI tools, enabling seamless integration between
the Aegis tool system and PydanticAI's LLM framework.
"""

from typing import Any, Callable
from aegis.tools.base_tool import Tool, ToolResult


def create_pydantic_tool(aegis_tool: Tool) -> Callable:
    """Convert an Aegis Tool to a PydanticAI-compatible function.
    
    This function creates a wrapper around an Aegis Tool that can be used
    as a PydanticAI tool. The wrapper preserves the tool's name, description,
    and parameter schema while adapting the execution interface.
    
    Args:
        aegis_tool: Aegis Tool instance to convert
        
    Returns:
        Callable that can be used as a PydanticAI tool
        
    Example:
        ```python
        from aegis.tools.filesystem import FileSystemTool
        from pydantic_ai import Agent
        
        fs_tool = FileSystemTool()
        pydantic_fs = create_pydantic_tool(fs_tool)
        
        agent = Agent(
            model="claude-3-5-sonnet",
            tools=[pydantic_fs]
        )
        ```
    """
    async def tool_function(**kwargs: Any) -> dict[str, Any]:
        """Generated tool function wrapper.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            Dictionary with success status and data or error
        """
        result: ToolResult = await aegis_tool.execute(**kwargs)
        
        if result.success:
            return {"success": True, "data": result.data}
        else:
            return {"success": False, "error": result.error}
    
    # Set function name and docstring from tool
    tool_function.__name__ = aegis_tool.name
    tool_function.__doc__ = aegis_tool.description
    
    return tool_function


def create_toolset_from_registry(registry: Any) -> list[Callable]:
    """Create a list of PydanticAI tools from the tool registry.
    
    This function iterates through all registered tools and converts them
    to PydanticAI-compatible functions, creating a toolset that can be
    passed to a PydanticAI Agent.
    
    Args:
        registry: ToolRegistry instance containing registered tools
        
    Returns:
        List of PydanticAI-compatible tool functions
        
    Example:
        ```python
        from aegis.tools.registry import get_registry
        from aegis.core.tool_bridge import create_toolset_from_registry
        from pydantic_ai import Agent
        
        registry = get_registry()
        toolset = create_toolset_from_registry(registry)
        
        agent = Agent(
            model="claude-3-5-sonnet",
            tools=toolset
        )
        ```
    """
    tools = []
    
    for tool_name in registry.list_available_tools():
        tool = registry.get_tool(tool_name)
        if tool:
            tools.append(create_pydantic_tool(tool))
    
    return tools
