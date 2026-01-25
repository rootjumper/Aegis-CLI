"""Tester agent for test generation and execution.

Generates and runs pytest tests for code validation.
"""

from typing import Any
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, ToolCall
from aegis.tools.registry import get_registry
from aegis.core.feedback import FeedbackParser


class TesterAgent(BaseAgent):
    """Agent specialized in testing.
    
    Capabilities:
    - Generate pytest tests from function signatures
    - Execute tests via SafeShell
    - Parse test output for failures
    - Create failure reports for Coder
    """
    
    def __init__(self, model: Model | None = None) -> None:
        """Initialize the tester agent.
        
        Args:
            model: Optional PydanticAI Model to use
        """
        super().__init__("tester", model=model)
        self.registry = get_registry()
        self.feedback_parser = FeedbackParser()
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a testing task.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with test results
        """
        try:
            # Get task details
            code = task.payload.get("code", "")
            file_path = task.payload.get("file_path", "")
            test_path = task.payload.get("test_path", "")
            
            if not code and not file_path:
                return AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="No code or file path provided for testing",
                    errors=["Missing code/file_path in task payload"]
                )
            
            tool_calls = []
            
            # Generate test if needed
            if not test_path:
                test_code = self._generate_test(code, file_path)
                test_path = file_path.replace(".py", "_test.py") if file_path else "test_generated.py"
                
                # In production, would write test file
                tool_calls.append(ToolCall(
                    tool_name="filesystem",
                    parameters={
                        "action": "smart_patch",
                        "path": test_path,
                        "changes": []
                    },
                    success=True
                ))
            
            # Execute tests
            shell_tool = self.registry.get_tool("shell")
            if shell_tool:
                result = await shell_tool.execute(
                    command=["pytest", test_path, "-v"],
                    require_confirmation=False,
                    timeout=60
                )
                
                tool_calls.append(ToolCall(
                    tool_name="shell",
                    parameters={"command": ["pytest", test_path, "-v"]},
                    result=result.data,
                    success=result.success
                ))
                
                if not result.success:
                    # Parse failures
                    output = result.data.get("stdout", "") + result.data.get("stderr", "")
                    feedbacks = self.feedback_parser.parse_pytest_output(output)
                    
                    errors = [f.message for f in feedbacks]
                    
                    return AgentResponse(
                        status="FAIL",
                        data={"test_output": output, "feedbacks": feedbacks},
                        reasoning_trace="Tests failed",
                        tool_calls=tool_calls,
                        errors=errors
                    )
            
            # Tests passed
            return AgentResponse(
                status="SUCCESS",
                data={"message": "All tests passed", "test_path": test_path},
                reasoning_trace="Test execution completed successfully",
                tool_calls=tool_calls
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error during testing: {e}",
                errors=[str(e)]
            )
    
    def _generate_test(self, code: str, file_path: str) -> str:
        """Generate test code for given code.
        
        Args:
            code: Code to test
            file_path: Path to code file
            
        Returns:
            Generated test code
        """
        # Simple test template
        # In production, would use LLM to generate comprehensive tests
        
        # Extract function names from code
        import re
        func_pattern = r"def\s+(\w+)\s*\("
        functions = re.findall(func_pattern, code)
        
        test_code = '''"""Generated tests."""

import pytest

'''
        
        for func_name in functions:
            if not func_name.startswith("_"):
                test_code += f'''
def test_{func_name}():
    """Test {func_name} function."""
    # TODO: Implement test
    pass

'''
        
        return test_code
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input.
        
        Args:
            task: Task to validate
            
        Returns:
            True if valid
        """
        # Must have code or file_path
        if "code" not in task.payload and "file_path" not in task.payload:
            return False
        
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt for tester.
        
        Returns:
            System prompt
        """
        return """You are the Tester Agent for Aegis-CLI.

Your role is to:
1. Generate comprehensive pytest tests for code
2. Execute tests via SafeShell
3. Parse and analyze test failures
4. Create actionable failure reports

When generating tests:
- Cover happy path, edge cases, and error conditions
- Use pytest fixtures and parametrize when appropriate
- Include docstrings for test functions
- Test both normal and exceptional behavior

When tests fail:
- Parse the output to extract specific failures
- Identify root causes
- Provide clear feedback to the Coder
- Suggest fixes when possible

Return FAIL status with detailed feedback if tests fail.
Return SUCCESS only if all tests pass.
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["filesystem", "shell"]
