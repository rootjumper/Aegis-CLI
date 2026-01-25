"""Coder agent for code generation.

Generates type-annotated Python code using best practices.
"""

from typing import Any

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, ToolCall
from aegis.tools.registry import get_registry


class CoderAgent(BaseAgent):
    """Agent specialized in code generation.
    
    Generates high-quality Python code with:
    - Type annotations
    - Docstrings
    - PEP8 compliance
    - Security best practices
    """
    
    def __init__(self) -> None:
        """Initialize the coder agent."""
        super().__init__("coder")
        self.registry = get_registry()
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a code generation task.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with generated code
        """
        try:
            # Get task details
            description = task.payload.get("description", "")
            file_path = task.payload.get("file_path", "")
            
            # Check for previous attempts and feedback
            previous_attempt = task.context.get("previous_attempt")
            test_feedback = task.context.get("test_feedback", [])
            review_feedback = task.context.get("review_feedback", [])
            
            # In production, would use PydanticAI/LLM here
            # For now, create placeholder implementation
            
            reasoning = f"Generating code for: {description}"
            if previous_attempt:
                reasoning += f"\nIncorporating feedback from previous attempt"
            if test_feedback:
                reasoning += f"\nAddressing test failures: {', '.join(test_feedback[:3])}"
            if review_feedback:
                reasoning += f"\nAddressing review comments: {', '.join(review_feedback[:3])}"
            
            # Placeholder code generation
            generated_code = self._generate_placeholder_code(description)
            
            tool_calls = []
            
            # If file_path is provided, write to file
            if file_path:
                fs_tool = self.registry.get_tool("filesystem")
                if fs_tool:
                    # For placeholder, we'll just track the tool call
                    tool_calls.append(ToolCall(
                        tool_name="filesystem",
                        parameters={
                            "action": "smart_patch",
                            "path": file_path,
                            "changes": []
                        },
                        success=True
                    ))
            
            return AgentResponse(
                status="SUCCESS",
                data={
                    "code": generated_code,
                    "file_path": file_path,
                    "description": description
                },
                reasoning_trace=reasoning,
                tool_calls=tool_calls
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error generating code: {e}",
                errors=[str(e)]
            )
    
    def _generate_placeholder_code(self, description: str) -> str:
        """Generate placeholder code based on description.
        
        Args:
            description: Code description
            
        Returns:
            Generated code
        """
        # Simple template-based code generation
        # In production, would use LLM
        
        if "hello world" in description.lower():
            return '''def hello_world() -> str:
    """Return a hello world message.
    
    Returns:
        Greeting message
    """
    return "Hello, World!"
'''
        
        # Generic function template
        return '''def generated_function() -> None:
    """Generated function placeholder.
    
    This function was generated based on the description:
    {description}
    """
    pass
'''.format(description=description)
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input.
        
        Args:
            task: Task to validate
            
        Returns:
            True if valid
        """
        # Must have description
        if "description" not in task.payload:
            return False
        
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt for coder.
        
        Returns:
            System prompt
        """
        return """You are the Coder Agent for Aegis-CLI.

Your role is to generate high-quality Python code that:
- Uses type hints (Python 3.11+ with | syntax)
- Includes comprehensive docstrings (Google style)
- Follows PEP8 strictly
- Implements security best practices:
  * No eval() or exec()
  * No hardcoded secrets
  * Input validation
  * Proper error handling
- Uses async/await where appropriate
- Prefers smart_patch for surgical edits over full rewrites

Before coding:
1. Request context via ContextTool if needed
2. Analyze requirements thoroughly
3. Consider edge cases and error handling

If you receive feedback from Tester or Critic:
- Address ALL issues before proceeding
- Explain your fixes in the reasoning trace
- Don't repeat the same mistakes
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["filesystem", "context"]
