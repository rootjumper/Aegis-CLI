"""Base agent contract for Aegis-CLI agents.

This module defines the abstract base class and data models that all agents
must implement to participate in the Aegis framework.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal
from pydantic import BaseModel, Field
from pydantic_ai.models import Model

from aegis.core.mcp_client import MCPManager, MCPServerConfig


class AgentTask(BaseModel):
    """Represents a task to be processed by an agent.
    
    Attributes:
        id: Unique task identifier
        type: Task type (e.g., "code", "review", "test")
        payload: Task-specific data
        dependencies: List of task IDs that must complete first
        context: Additional context information
        max_retries: Maximum number of retry attempts
    """
    id: str
    type: str
    payload: dict[str, Any]
    dependencies: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3


class ToolCall(BaseModel):
    """Represents a tool invocation by an agent.
    
    Attributes:
        tool_name: Name of the tool being called
        parameters: Tool parameters
        result: Result returned by the tool
        success: Whether the tool call succeeded
        error: Error message if the call failed
    """
    tool_name: str
    parameters: dict[str, Any]
    result: Any = None
    success: bool = True
    error: str | None = None


class AgentResponse(BaseModel):
    """Response from an agent after processing a task.
    
    Attributes:
        status: Execution status
        data: Response data
        reasoning_trace: Explanation of agent's reasoning
        tool_calls: List of tool calls made during execution
        next_actions: Suggested next steps
        errors: List of errors encountered
    """
    status: Literal["SUCCESS", "FAIL", "RETRY", "PENDING"]
    data: dict[str, Any]
    reasoning_trace: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for all Aegis agents.
    
    All agents must inherit from this class and implement the required
    abstract methods. Agents are responsible for processing tasks,
    validating inputs, and coordinating with tools.
    """
    
    def __init__(
        self, 
        name: str,
        mcp_servers: list[MCPServerConfig] | None = None,
        model: Model | None = None
    ) -> None:
        """Initialize the agent.
        
        Args:
            name: Agent name/identifier
            mcp_servers: Optional list of MCP server configurations
            model: Optional PydanticAI Model to use. If not provided,
                   uses default model from configuration
        """
        self.name = name
        self.mcp_servers = mcp_servers or []
        self._mcp_manager: MCPManager | None = None
        self._model = model
    
    @abstractmethod
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a task and return a response.
        
        This is the main entry point for agent execution. The agent should
        analyze the task, use appropriate tools, and return a structured
        response.
        
        Args:
            task: The task to process
            
        Returns:
            AgentResponse containing execution results
        """
        pass
    
    @abstractmethod
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input before processing.
        
        Perform pre-execution checks to ensure the task has all required
        data and is properly formatted.
        
        Args:
            task: The task to validate
            
        Returns:
            True if the task is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.
        
        Returns a prompt that describes the agent's role, capabilities,
        and guidelines for the LLM.
        
        Returns:
            System prompt string
        """
        pass
    
    @abstractmethod
    def get_required_tools(self) -> list[str]:
        """Get the list of tools required by this agent.
        
        Returns:
            List of tool names needed for agent operation
        """
        pass
    
    @asynccontextmanager
    async def run_with_mcp(self) -> AsyncIterator[list[Any]]:
        """Context manager for running agent with MCP tools.

        Initializes MCP server connections and yields MCP servers that
        can be used as toolsets in PydanticAI Agent.

        Yields:
            List of MCP servers to use as toolsets

        Example:
            ```python
            from pydantic_ai import Agent

            async with agent.run_with_mcp() as mcp_toolsets:
                # Use MCP servers as toolsets with PydanticAI Agent
                pydantic_agent = Agent(
                    model="claude-3-5-sonnet",
                    toolsets=mcp_toolsets,
                    system_prompt=agent.get_system_prompt()
                )
                result = await pydantic_agent.run(task_prompt)
            ```
        """
        if not self.mcp_servers:
            # No MCP servers configured, yield empty list
            yield []
            return

        # Create MCP manager
        self._mcp_manager = MCPManager(self.mcp_servers)

        # Run servers and yield them as toolsets
        async with self._mcp_manager.run_servers() as servers:
            yield servers

        # Cleanup
        self._mcp_manager = None
    
    def get_model(self) -> Model:
        """Get the model to use for this agent.
        
        Returns the model specified during initialization, or the default
        model from configuration if none was specified.
        
        Returns:
            PydanticAI Model instance
            
        Raises:
            ValueError: If no model is configured
        """
        if self._model is not None:
            return self._model
        
        # Import here to avoid circular dependency
        from aegis.core.llm_config import get_default_model
        
        return get_default_model()
    
    def get_mcp_server_names(self) -> list[str]:
        """Get names of configured MCP servers.
        
        Returns:
            List of server names
        """
        return [server.name for server in self.mcp_servers]
