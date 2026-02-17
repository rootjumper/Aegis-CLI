"""Coder agent for code generation.

Generates type-annotated Python code using best practices.
"""

from typing import Any
from pydantic_ai.models import Model

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
    
    def __init__(self, model: Model | None = None) -> None:
        """Initialize the coder agent.
        
        Args:
            model: Optional PydanticAI Model to use
        """
        super().__init__("coder", model=model)
        self.registry = get_registry()
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a code generation task using LLM.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with generated code
        """
        from pydantic_ai import Agent as PydanticAgent
        from aegis.core.tool_bridge import create_toolset_from_registry
        
        try:
            # Get task details
            description = task.payload.get("description", "")
            file_path = task.payload.get("file_path", "")
            
            # Check for previous attempts and feedback
            previous_attempt = task.context.get("previous_attempt")
            test_feedback = task.context.get("test_feedback", [])
            review_feedback = task.context.get("review_feedback", [])
            
            # Build comprehensive prompt with feedback
            prompt = f"Generate Python code: {description}"
            
            if previous_attempt:
                prompt += "\n\nThis is a retry. Previous attempt did not meet requirements."
            
            if test_feedback:
                feedback_str = "\n".join(f"- {fb}" for fb in test_feedback[:5])
                prompt += f"\n\n**Test Failures to Fix:**\n{feedback_str}"
            
            if review_feedback:
                feedback_str = "\n".join(f"- {fb}" for fb in review_feedback[:5])
                prompt += f"\n\n**Review Comments to Address:**\n{feedback_str}"
            
            # Get model and tools
            model = self.get_model()
            toolset = create_toolset_from_registry(self.registry)
            
            # Create PydanticAI agent with tools
            pydantic_agent = PydanticAgent(
                model=model,
                tools=toolset,
                system_prompt=self.get_system_prompt()
            )
            
            # Generate code using LLM
            result = await pydantic_agent.run(prompt)
            
            # Extract generated code from response
            # The LLM should return the code as text
            generated_code = str(result.data)
            
            # Build reasoning trace
            reasoning = f"Generated code for: {description}"
            if previous_attempt:
                reasoning += "\nIncorporated feedback from previous attempt"
            if test_feedback:
                reasoning += f"\nFixed {len(test_feedback)} test failures"
            if review_feedback:
                reasoning += f"\nAddressed {len(review_feedback)} review comments"
            
            # Track tool calls
            tool_calls = []
            
            # If file_path is provided, write to file
            if file_path:
                fs_tool = self.registry.get_tool("filesystem")
                if fs_tool:
                    write_result = await fs_tool.execute(
                        action="write_file",
                        path=file_path,
                        content=generated_code
                    )
                    
                    tool_calls.append(ToolCall(
                        tool_name="filesystem",
                        parameters={
                            "action": "write_file",
                            "path": file_path,
                            "content": generated_code[:100] + "..."  # Truncate for logging
                        },
                        result=write_result.data,
                        success=write_result.success,
                        error=write_result.error
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
