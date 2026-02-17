"""Orchestrator agent for task decomposition and delegation.

The orchestrator is responsible for:
- Parsing user prompts into structured tasks
- Building task dependency graphs
- Delegating to specialized agents
- Coordinating the verification cycle
"""

import uuid
from pathlib import Path
from typing import Any
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, MCPServerConfig
from aegis.core.mcp_client import load_mcp_config, filter_servers_by_name
from aegis.tools.registry import get_registry


class OrchestratorAgent(BaseAgent):
    """Orchestrator for task decomposition and coordination.
    
    This agent analyzes user prompts and delegates work to specialized
    agents while managing dependencies and verification.
    """
    
    def __init__(
        self,
        mcp_config_path: str | Path | None = None,
        model: Model | None = None
    ) -> None:
        """Initialize the orchestrator agent.
        
        Args:
            mcp_config_path: Optional path to MCP configuration file
            model: Optional PydanticAI Model to use
        """
        super().__init__("orchestrator", model=model)
        self.registry = get_registry()
        self.mcp_config_path = mcp_config_path
        self._mcp_servers: list[MCPServerConfig] = []
        
        # Load MCP config if available
        if mcp_config_path:
            try:
                self._mcp_servers = load_mcp_config(mcp_config_path)
            except (FileNotFoundError, ValueError):
                # Config file not found or invalid, continue without MCP
                pass
    
    def get_mcp_servers_for_agent(
        self, 
        agent_name: str,
        server_names: list[str] | None = None
    ) -> list[MCPServerConfig]:
        """Get MCP servers to equip a specific agent with.
        
        Args:
            agent_name: Name of the agent
            server_names: Optional list of server names to filter by
            
        Returns:
            List of MCP server configurations for the agent
        """
        if not self._mcp_servers:
            return []
        
        if server_names:
            return filter_servers_by_name(self._mcp_servers, server_names)
        
        # Return all servers by default
        return self._mcp_servers.copy()
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a task by delegating to appropriate agents.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with execution results
        """
        try:
            # For now, simple implementation
            # In full implementation, would use PydanticAI to analyze prompt
            prompt = task.payload.get("prompt", "")
            
            if not prompt:
                return AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="No prompt provided",
                    errors=["Missing prompt in task payload"]
                )
            
            # Decompose prompt into tasks
            subtasks = await self.decompose_prompt(prompt)
            
            # For initial implementation, return SUCCESS with subtasks
            return AgentResponse(
                status="SUCCESS",
                data={"subtasks": subtasks},
                reasoning_trace=f"Decomposed prompt into {len(subtasks)} tasks"
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error in orchestration: {e}",
                errors=[str(e)]
            )
    
    async def decompose_prompt(self, prompt: str) -> list[dict[str, Any]]:
        """Decompose a user prompt into structured tasks using LLM.
        
        Args:
            prompt: User prompt
            
        Returns:
            List of task dictionaries
        """
        from pydantic import BaseModel, Field
        
        # Define output structure for LLM
        class TaskDecomposition(BaseModel):
            """Structured task decomposition from user prompt."""
            tasks: list[dict[str, Any]] = Field(
                description="List of tasks with type, description, and priority"
            )
            reasoning: str = Field(
                description="Explanation of task breakdown"
            )
        
        try:
            # Get model
            model = self.get_model()
            
            # Create PydanticAI agent for task decomposition
            pydantic_agent = PydanticAgent(
                model=model,
                result_type=TaskDecomposition,
                system_prompt=self.get_system_prompt()
            )
            
            # Build prompt for task decomposition
            decomposition_prompt = f"""Analyze this user request and break it down into actionable tasks:

"{prompt}"

Create a structured task breakdown with:
- Task type (one of: "code", "test", "review", "documentation")
- Detailed description of what needs to be done
- Priority (1 = highest)

Each task should be atomic and actionable. Consider:
- What code needs to be written?
- What tests are needed?
- What documentation should be updated?
- Are there review/quality requirements?

Return the tasks in order of execution priority."""
            
            # Run LLM decomposition
            result = await pydantic_agent.run(decomposition_prompt)
            
            # Extract tasks from LLM response
            tasks = result.data.tasks
            
            # Validate and normalize task structure
            normalized_tasks = []
            for task in tasks:
                normalized_task = {
                    "type": task.get("type", "code"),
                    "description": task.get("description", prompt),
                    "priority": task.get("priority", 1)
                }
                normalized_tasks.append(normalized_task)
            
            # If no tasks generated, fall back to default
            if not normalized_tasks:
                normalized_tasks.append({
                    "type": "code",
                    "description": prompt,
                    "priority": 1
                })
            
            return normalized_tasks
            
        except Exception as e:
            # Fallback to simple keyword-based decomposition if LLM fails
            tasks = []
            
            # Check for code-related keywords
            code_keywords = ["create", "implement", "generate", "write", "code", "function"]
            if any(keyword in prompt.lower() for keyword in code_keywords):
                tasks.append({
                    "type": "code",
                    "description": f"Generate code: {prompt}",
                    "priority": 1
                })
            
            # Default to code task if nothing matches
            if not tasks:
                tasks.append({
                    "type": "code",
                    "description": prompt,
                    "priority": 1
                })
            
            return tasks
    
    async def execute_dag(
        self,
        tasks: list[AgentTask]
    ) -> dict[str, AgentResponse]:
        """Execute tasks respecting dependencies.
        
        Args:
            tasks: List of tasks to execute
            
        Returns:
            Dictionary mapping task IDs to responses
        """
        # Simple sequential execution for now
        # In production, would do topological sort and parallel execution
        
        results: dict[str, AgentResponse] = {}
        
        for task in tasks:
            # Check dependencies
            dependencies_met = all(
                dep in results and results[dep].status == "SUCCESS"
                for dep in task.dependencies
            )
            
            if not dependencies_met:
                results[task.id] = AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="Dependencies not met",
                    errors=["Required dependencies failed or incomplete"]
                )
                continue
            
            # Would delegate to appropriate agent here
            # For now, just mark as pending
            results[task.id] = AgentResponse(
                status="PENDING",
                data={},
                reasoning_trace="Task queued for execution"
            )
        
        return results
    
    def should_retry(self, response: AgentResponse, attempt: int) -> bool:
        """Determine if a failed task should be retried.
        
        Args:
            response: Agent response
            attempt: Current attempt number
            
        Returns:
            True if should retry
        """
        if response.status == "SUCCESS":
            return False
        
        # Retry FAIL and RETRY statuses
        if response.status in ["FAIL", "RETRY"]:
            # Check for non-retriable errors
            non_retriable = ["invalid_input", "missing_dependency"]
            for error in response.errors:
                if any(nr in error.lower() for nr in non_retriable):
                    return False
            
            return True
        
        return False
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input.
        
        Args:
            task: Task to validate
            
        Returns:
            True if valid
        """
        # Check required fields
        if "prompt" not in task.payload:
            return False
        
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt for orchestrator.
        
        Returns:
            System prompt
        """
        return """You are the Orchestrator Agent for Aegis-CLI, an expert at breaking down complex software development tasks.

Your role is to analyze user prompts and decompose them into structured, actionable subtasks that can be executed by specialized agents.

**Available Agent Types:**
- **code**: For generating Python code implementations
- **test**: For creating and running pytest tests
- **review**: For code quality and security reviews
- **documentation**: For updating README, docstrings, and API docs

**Task Decomposition Guidelines:**
1. Break complex requests into atomic, sequential tasks
2. Identify all required components (code, tests, docs)
3. Set realistic priorities (1 = highest/first)
4. Ensure each task has a clear, actionable description
5. Consider dependencies between tasks

**Example Decomposition:**
User: "Create a calculator function with tests"

Tasks:
1. {"type": "code", "description": "Implement calculator function with add, subtract, multiply, divide operations", "priority": 1}
2. {"type": "test", "description": "Create comprehensive pytest tests for calculator with edge cases", "priority": 2}
3. {"type": "documentation", "description": "Add docstrings and usage examples to calculator", "priority": 3}

**Output Format:**
Return a JSON structure with:
- "tasks": Array of task objects (type, description, priority)
- "reasoning": Brief explanation of your decomposition strategy

Always consider:
- Code quality and security requirements
- Test coverage needs
- Documentation completeness
- Logical execution order
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["context"]
