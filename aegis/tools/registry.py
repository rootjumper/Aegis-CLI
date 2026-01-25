"""Tool registry for dynamic tool discovery.

Provides automatic discovery and registration of all available tools.
"""

import importlib
import inspect
from typing import Any

from aegis.tools.base_tool import Tool


class ToolRegistry:
    """Registry for managing and discovering tools.
    
    Automatically detects and registers all Tool subclasses
    in the tools module.
    """
    
    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}
        self._initialized = False
    
    def _discover_tools(self) -> None:
        """Discover and register all tools."""
        if self._initialized:
            return
        
        # Import all tool modules
        tool_modules = [
            "aegis.tools.filesystem",
            "aegis.tools.shell",
            "aegis.tools.context"
        ]
        
        for module_name in tool_modules:
            try:
                module = importlib.import_module(module_name)
                
                # Find all Tool subclasses
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, Tool) and 
                        obj != Tool):
                        # Instantiate and register
                        try:
                            tool_instance = obj()
                            self._tools[tool_instance.name] = tool_instance
                        except Exception:
                            # Skip tools that fail to instantiate
                            pass
            except ImportError:
                # Skip modules that fail to import
                pass
        
        self._initialized = True
    
    def get_tool(self, name: str) -> Tool | None:
        """Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        if not self._initialized:
            self._discover_tools()
        
        return self._tools.get(name)
    
    def list_available_tools(self) -> list[str]:
        """Get list of available tool names.
        
        Returns:
            List of tool names
        """
        if not self._initialized:
            self._discover_tools()
        
        return list(self._tools.keys())
    
    def get_all_tools(self) -> dict[str, Tool]:
        """Get all registered tools.
        
        Returns:
            Dictionary mapping tool names to Tool instances
        """
        if not self._initialized:
            self._discover_tools()
        
        return self._tools.copy()
    
    def register_tool(self, tool: Tool) -> None:
        """Manually register a tool.
        
        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool


# Global registry instance
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry.
    
    Returns:
        ToolRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
