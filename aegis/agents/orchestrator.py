"""Orchestrator agent for task decomposition and delegation.

The orchestrator is responsible for:
- Parsing user prompts into structured tasks
- Building task dependency graphs
- Delegating to specialized agents
- Coordinating the verification cycle
"""

import uuid
from typing import Any
from pydantic_ai import Agent as PydanticAgent

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse
from aegis.tools.registry import get_registry


class OrchestratorAgent(BaseAgent):
    """Orchestrator for task decomposition and coordination.
    
    This agent analyzes user prompts and delegates work to specialized
    agents while managing dependencies and verification.
    """
    
    def __init__(self) -> None:
        """Initialize the orchestrator agent."""
        super().__init__("orchestrator")
        self.registry = get_registry()
    
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
        """Decompose a user prompt into structured tasks.
        
        Args:
            prompt: User prompt
            
        Returns:
            List of task dictionaries
        """
        # Simple keyword-based decomposition
        # In production, would use LLM for intelligent analysis
        
        tasks = []
        
        # Check for code-related keywords
        code_keywords = ["create", "implement", "generate", "write", "code", "function"]
        if any(keyword in prompt.lower() for keyword in code_keywords):
            tasks.append({
                "type": "code",
                "description": f"Generate code: {prompt}",
                "priority": 1
            })
        
        # Check for test-related keywords
        test_keywords = ["test", "verify", "validate"]
        if any(keyword in prompt.lower() for keyword in test_keywords):
            tasks.append({
                "type": "test",
                "description": f"Create tests: {prompt}",
                "priority": 2
            })
        
        # Check for documentation keywords
        doc_keywords = ["document", "readme", "docs", "documentation"]
        if any(keyword in prompt.lower() for keyword in doc_keywords):
            tasks.append({
                "type": "documentation",
                "description": f"Update documentation: {prompt}",
                "priority": 3
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
        return """You are the Orchestrator Agent for Aegis-CLI.
        
Your role is to:
1. Analyze user prompts and break them down into actionable tasks
2. Identify dependencies between tasks
3. Delegate tasks to specialized agents (Coder, Tester, Critic, Janitor)
4. Coordinate the verification cycle to ensure quality

You should create a structured plan with clear dependencies and priorities.
Always consider:
- What needs to be coded
- What needs to be tested
- What needs to be documented
- Security and quality requirements
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["context"]
