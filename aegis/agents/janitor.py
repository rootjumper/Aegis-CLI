"""Janitor agent for documentation maintenance.

Keeps documentation in sync with code changes.
"""

from typing import Any

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, ToolCall
from aegis.tools.registry import get_registry


class JanitorAgent(BaseAgent):
    """Agent specialized in documentation maintenance.
    
    Responsibilities:
    - Update README.md with new features
    - Sync docstrings with code changes
    - Generate API documentation
    - Clean up unused imports
    """
    
    def __init__(self) -> None:
        """Initialize the janitor agent."""
        super().__init__("janitor")
        self.registry = get_registry()
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a documentation task.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with documentation results
        """
        try:
            # Get task details
            doc_type = task.payload.get("doc_type", "general")
            target_file = task.payload.get("target_file", "README.md")
            changes = task.payload.get("changes", [])
            
            tool_calls = []
            
            if doc_type == "readme":
                # Update README
                result = await self._update_readme(target_file, changes)
                tool_calls.extend(result.get("tool_calls", []))
                
            elif doc_type == "docstring":
                # Update docstrings
                result = await self._update_docstrings(changes)
                tool_calls.extend(result.get("tool_calls", []))
                
            elif doc_type == "api":
                # Generate API docs
                result = await self._generate_api_docs()
                tool_calls.extend(result.get("tool_calls", []))
                
            elif doc_type == "cleanup":
                # Clean up code
                result = await self._cleanup_code(changes)
                tool_calls.extend(result.get("tool_calls", []))
            
            return AgentResponse(
                status="SUCCESS",
                data={"message": f"Documentation updated: {doc_type}"},
                reasoning_trace=f"Completed {doc_type} documentation task",
                tool_calls=tool_calls
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error updating documentation: {e}",
                errors=[str(e)]
            )
    
    async def _update_readme(
        self,
        readme_path: str,
        changes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Update README with new features.
        
        Args:
            readme_path: Path to README file
            changes: List of changes to document
            
        Returns:
            Result dictionary
        """
        # In production, would read README, analyze structure, and add sections
        
        tool_calls = [
            ToolCall(
                tool_name="filesystem",
                parameters={
                    "action": "read_file",
                    "path": readme_path
                },
                success=True
            )
        ]
        
        return {"tool_calls": tool_calls}
    
    async def _update_docstrings(
        self,
        changes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Update docstrings to match code changes.
        
        Args:
            changes: List of code changes
            
        Returns:
            Result dictionary
        """
        # In production, would analyze function signatures and update docstrings
        
        tool_calls = []
        
        for change in changes:
            file_path = change.get("file_path", "")
            if file_path:
                tool_calls.append(ToolCall(
                    tool_name="filesystem",
                    parameters={
                        "action": "smart_patch",
                        "path": file_path,
                        "changes": []
                    },
                    success=True
                ))
        
        return {"tool_calls": tool_calls}
    
    async def _generate_api_docs(self) -> dict[str, Any]:
        """Generate API documentation.
        
        Returns:
            Result dictionary
        """
        # In production, would use tools like sphinx or pdoc
        
        tool_calls = [
            ToolCall(
                tool_name="shell",
                parameters={
                    "command": ["python", "-m", "pydoc", "-w", "aegis"]
                },
                success=True
            )
        ]
        
        return {"tool_calls": tool_calls}
    
    async def _cleanup_code(
        self,
        files: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Clean up unused imports and format code.
        
        Args:
            files: List of files to clean
            
        Returns:
            Result dictionary
        """
        # In production, would use tools like autoflake, isort
        
        tool_calls = []
        
        for file_info in files:
            file_path = file_info.get("path", "")
            if file_path:
                tool_calls.append(ToolCall(
                    tool_name="shell",
                    parameters={
                        "command": ["python", "-m", "isort", file_path]
                    },
                    success=True
                ))
        
        return {"tool_calls": tool_calls}
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input.
        
        Args:
            task: Task to validate
            
        Returns:
            True if valid
        """
        # Must have doc_type
        if "doc_type" not in task.payload:
            return False
        
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt for janitor.
        
        Returns:
            System prompt
        """
        return """You are the Janitor Agent for Aegis-CLI.

Your role is to maintain documentation quality:

1. **README Updates**:
   - Add new features to feature lists
   - Update installation instructions
   - Keep examples current
   - Maintain changelog

2. **Docstring Maintenance**:
   - Ensure docstrings match function signatures
   - Use Google style consistently
   - Include parameter descriptions and return types
   - Add usage examples for complex functions

3. **API Documentation**:
   - Generate comprehensive API docs
   - Keep docs in sync with code
   - Include examples and best practices

4. **Code Cleanup**:
   - Remove unused imports
   - Fix formatting issues
   - Organize imports (stdlib, third-party, local)

Always preserve existing documentation structure and style.
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["filesystem", "shell"]
