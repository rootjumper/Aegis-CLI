"""Base tool interface for Aegis-CLI.

This module defines the abstract Tool class that all tools must implement.
"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result from a tool execution.
    
    Attributes:
        success: Whether the tool execution succeeded
        data: Result data
        error: Error message if execution failed
    """
    success: bool = True
    data: Any = None
    error: str | None = None


class Tool(ABC):
    """Abstract base class for all Aegis tools.
    
    Tools provide functionality to agents such as file operations,
    shell commands, memory access, etc.
    """
    
    def __init__(self) -> None:
        """Initialize the tool."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name.
        
        Returns:
            Tool name
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description.
        
        Returns:
            Tool description
        """
        pass
    
    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters.
        
        Returns:
            JSON schema dictionary
        """
        pass
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult containing execution results
        """
        pass
    
    def validate_params(self, params: dict[str, Any]) -> bool:
        """Validate parameters against the schema.
        
        Args:
            params: Parameters to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Basic validation - can be enhanced with jsonschema
        schema = self.parameters_schema
        required = schema.get("required", [])
        
        # Check required parameters
        for param in required:
            if param not in params:
                return False
        
        return True
