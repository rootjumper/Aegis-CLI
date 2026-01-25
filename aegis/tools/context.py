"""Context tool for agent memory management.

Provides memory interface for storing and retrieving context information.
"""

from typing import Any

from aegis.tools.base_tool import Tool, ToolResult
from aegis.core.state import get_state_manager


class ContextTool(Tool):
    """Tool for agent memory and context management.
    
    Provides capabilities for storing, retrieving, and searching
    contextual information across agent interactions.
    """
    
    def __init__(self) -> None:
        """Initialize the context tool."""
        super().__init__()
        self.state_manager = get_state_manager()
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "context"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "Store and retrieve contextual information in agent memory"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["remember", "recall", "forget"],
                    "description": "Memory action to perform"
                },
                "key": {
                    "type": "string",
                    "description": "Memory key"
                },
                "value": {
                    "description": "Value to store (for remember)"
                },
                "agent": {
                    "type": "string",
                    "description": "Agent name for filtering"
                },
                "ttl": {
                    "type": "integer",
                    "description": "Time to live in seconds (for remember)",
                    "default": 3600
                }
            },
            "required": ["action", "key"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute memory operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with operation results
        """
        action = kwargs.get("action")
        key = kwargs.get("key")
        
        if not key:
            return ToolResult(success=False, error="Key is required")
        
        try:
            # Ensure database is initialized
            await self.state_manager.init_database()
            
            if action == "remember":
                value = kwargs.get("value")
                agent = kwargs.get("agent", "unknown")
                ttl = kwargs.get("ttl", 3600)
                
                await self.remember(key, value, agent, ttl)
                return ToolResult(
                    success=True,
                    data={"message": f"Stored value for key: {key}"}
                )
            
            elif action == "recall":
                agent = kwargs.get("agent")
                value = await self.recall(key, agent)
                
                if value is None:
                    return ToolResult(
                        success=False,
                        error=f"No value found for key: {key}"
                    )
                
                return ToolResult(success=True, data=value)
            
            elif action == "forget":
                await self.forget(key)
                return ToolResult(
                    success=True,
                    data={"message": f"Deleted key: {key}"}
                )
            
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def remember(
        self,
        key: str,
        value: Any,
        agent: str,
        ttl: int = 3600
    ) -> None:
        """Store a value in memory.
        
        Args:
            key: Memory key
            value: Value to store
            agent: Agent name
            ttl: Time to live in seconds
        """
        await self.state_manager.remember(key, value, agent, ttl)
    
    async def recall(
        self,
        key: str,
        agent: str | None = None
    ) -> Any:
        """Recall a value from memory.
        
        Args:
            key: Memory key
            agent: Optional agent name filter
            
        Returns:
            Stored value or None
        """
        return await self.state_manager.recall(key, agent)
    
    async def forget(self, key: str) -> None:
        """Delete a value from memory.
        
        Args:
            key: Memory key
        """
        await self.state_manager.forget(key)
