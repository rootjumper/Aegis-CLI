"""Tester agent for test generation and execution.

Generates and runs pytest tests for code validation.
"""

from typing import Any
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, ToolCall
from aegis.tools.registry import get_registry
from aegis.core.feedback import FeedbackParser
from aegis.core.llm_response_parser import LLMResponseParser


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
        self.parser = LLMResponseParser(strict=False, log_failures=True)
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a testing task using LLM to generate tests.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with test results
        """
        from pydantic_ai import Agent as PydanticAgent
        from aegis.core.tool_bridge import create_toolset_from_registry
        
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
            
            # Generate test if needed using LLM
            if not test_path:
                # Get model and tools
                model = self.get_model()
                toolset = create_toolset_from_registry(self.registry)
                
                # Create PydanticAI agent
                pydantic_agent = PydanticAgent(
                    model=model,
                    tools=toolset,
                    system_prompt=self.get_system_prompt()
                )
                
                # Build prompt for test generation
                test_prompt = f"""Generate comprehensive pytest tests for this Python code:

```python
{code}
```

Requirements:
- Cover happy path, edge cases, and error conditions
- Use pytest fixtures and parametrize where appropriate
- Include clear docstrings for each test function
- Test both normal and exceptional behavior
- Follow pytest best practices

Return ONLY the test code, no explanations."""
                
                # Generate tests using LLM
                result = await pydantic_agent.run(test_prompt)
                
                # Extract test code using universal parser
                test_code = self.parser.parse(result, content_type='code')
                
                # Validate the extracted test code
                is_valid, validation_error = self.parser.validate_code(test_code)
                if not is_valid:
                    return AgentResponse(
                        status="FAIL",
                        data={},
                        reasoning_trace=f"Generated test code has syntax errors: {validation_error}",
                        errors=[f"Invalid Python test code: {validation_error}"]
                    )
                
                # Determine test file path
                test_path = file_path.replace(".py", "_test.py") if file_path else "test_generated.py"
                
                # Write test file
                fs_tool = self.registry.get_tool("filesystem")
                if fs_tool:
                    write_result = await fs_tool.execute(
                        action="write_file",
                        path=test_path,
                        content=test_code
                    )
                    
                    tool_calls.append(ToolCall(
                        tool_name="filesystem",
                        parameters={
                            "action": "write_file",
                            "path": test_path,
                            "content": test_code[:100] + ("..." if len(test_code) > 100 else "")
                        },
                        result=write_result.data,
                        success=write_result.success,
                        error=write_result.error
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
                reasoning_trace="Test generation and execution completed successfully",
                tool_calls=tool_calls
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error during testing: {e}",
                errors=[str(e)]
            )
    
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
