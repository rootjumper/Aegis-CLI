"""Coder agent for code generation.

Generates type-annotated Python code using best practices.
"""

from typing import Any
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, ToolCall
from aegis.tools.registry import get_registry
from aegis.core.llm_response_parser import LLMResponseParser
from aegis.core.llm_logger import LLMLogger


class CoderAgent(BaseAgent):
    """Agent specialized in code generation.
    
    Generates high-quality code in multiple programming languages with:
    - Type annotations (for Python)
    - Proper documentation
    - Language-specific best practices
    - Security best practices
    """
    
    # Language detection map for file extensions
    _EXTENSION_MAP = {
        '.py': ('Python', 'python'),
        '.html': ('HTML', 'html'),
        '.htm': ('HTML', 'html'),
        '.css': ('CSS', 'css'),
        '.js': ('JavaScript', 'javascript'),
        '.mjs': ('JavaScript', 'javascript'),
        '.ts': ('TypeScript', 'typescript'),
        '.tsx': ('TypeScript TSX', 'tsx'),
        '.jsx': ('React JSX', 'jsx'),
        '.json': ('JSON', 'json'),
        '.yaml': ('YAML', 'yaml'),
        '.yml': ('YAML', 'yaml'),
        '.md': ('Markdown', 'markdown'),
        '.sql': ('SQL', 'sql'),
        '.sh': ('Shell', 'bash'),
        '.bash': ('Bash', 'bash'),
        '.rs': ('Rust', 'rust'),
        '.go': ('Go', 'go'),
        '.java': ('Java', 'java'),
        '.c': ('C', 'c'),
        '.cpp': ('C++', 'cpp'),
        '.h': ('C Header', 'c'),
        '.hpp': ('C++ Header', 'cpp'),
        '.cs': ('C#', 'csharp'),
        '.rb': ('Ruby', 'ruby'),
        '.php': ('PHP', 'php'),
        '.swift': ('Swift', 'swift'),
        '.kt': ('Kotlin', 'kotlin'),
        '.xml': ('XML', 'xml'),
    }
    
    def __init__(self, model: Model | None = None, verbose: bool = False) -> None:
        """Initialize the coder agent.
        
        Args:
            model: Optional PydanticAI Model to use
            verbose: Whether to enable verbose LLM logging
        """
        super().__init__("coder", model=model)
        self.registry = get_registry()
        self.parser = LLMResponseParser(strict=False, log_failures=True)
        self.llm_logger = LLMLogger(verbose=verbose)
    
    def _detect_language_from_path(self, file_path: str) -> tuple[str, str]:
        """Detect programming language and markdown tag from file path.
        
        Args:
            file_path: Path to file being generated
            
        Returns:
            Tuple of (language_name, markdown_tag)
            
        Examples:
            "src/app.py" → ("Python", "python")
            "index.html" → ("HTML", "html")
            "styles.css" → ("CSS", "css")
            "script.js" → ("JavaScript", "javascript")
        """
        from pathlib import Path
        
        if not file_path:
            return ('Python', 'python')
        
        ext = Path(file_path).suffix.lower()
        return self._EXTENSION_MAP.get(ext, ('Python', 'python'))
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a code generation task using LLM.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with generated code
        """
        from pydantic_ai import Agent as PydanticAgent
        import json
        
        try:
            # Get task details
            description = task.payload.get("description", "").strip()
            file_path = task.payload.get("file_path", "")
            context_info = task.payload.get("context", {})
            original_task = context_info.get("original_request", description)
            
            # Validate description
            if not description:
                return AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="Code description is empty or missing",
                    errors=["No code description provided. Cannot generate code without knowing what to create."]
                )
            
            # Check for previous attempts and feedback
            previous_attempt = task.context.get("previous_attempt")
            test_feedback = task.context.get("test_feedback", [])
            review_feedback = task.context.get("review_feedback", [])
            
            # Detect language from file path
            language_name, markdown_tag = self._detect_language_from_path(file_path)
            
            # Build language-specific prompt
            prompt = f"""Generate {language_name} code for: {description}

ORIGINAL REQUEST: {original_task}

TARGET FILE: {file_path}

CONTEXT:
{json.dumps(context_info, indent=2) if context_info else 'No additional context'}

REQUIREMENTS:
- Generate clean, production-ready {language_name} code
- Return ONLY the code itself
- Wrap in markdown code block: ```{markdown_tag}
... your {language_name} code here ...
```
- Do NOT use tool calls
- Do NOT save files yourself
- Do NOT include explanations outside the code block

CRITICAL: Return the code in this exact format:
```{markdown_tag}
// Your complete {language_name} code here
```

No other text before or after the code block."""
            
            if previous_attempt:
                prompt += "\n\nThis is a retry. Previous attempt did not meet requirements."
            
            if test_feedback:
                feedback_str = "\n".join(f"- {fb}" for fb in test_feedback[:5])
                prompt += f"\n\n**Test Failures to Fix:**\n{feedback_str}"
            
            if review_feedback:
                feedback_str = "\n".join(f"- {fb}" for fb in review_feedback[:5])
                prompt += f"\n\n**Review Comments to Address:**\n{feedback_str}"
            
            # Get model (NO TOOLS)
            model = self.get_model()
            
            # Create PydanticAI agent WITHOUT tools
            pydantic_agent = PydanticAgent(
                model=model,
                # NO tools - CoderAgent is text generation only
                system_prompt=self.get_system_prompt()
            )
            
            # LOG PROMPT
            interaction_id = self.llm_logger.log_prompt(
                agent_name="CoderAgent",
                prompt=prompt,
                model=str(model),
                system_prompt=self.get_system_prompt(),
                tools=[]  # No tools - text generation only
            )
            
            # Generate code using LLM
            result = await pydantic_agent.run(prompt)
            
            # Extract generated code from response using universal parser
            generated_code = self.parser.parse(result, content_type='code')
            
            # LOG RESPONSE
            self.llm_logger.log_response(
                interaction_id=interaction_id,
                agent_name="CoderAgent",
                response=result,
                extracted_content=generated_code,
                finish_reason="stop"
            )
            
            # Validate the extracted code with language-aware validation
            is_valid, validation_error = self.parser.validate_code(generated_code, language=markdown_tag)
            if not is_valid:
                return AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace=f"Generated code has syntax errors: {validation_error}",
                    errors=[f"Invalid {language_name} code: {validation_error}"]
                )
            
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
                    
                    # LOG FILE OPERATION
                    self.llm_logger.log_file_operation(
                        agent_name="CoderAgent",
                        operation="write_file",
                        file_path=file_path,
                        success=write_result.success,
                        content_preview=generated_code[:200],
                        error=write_result.error
                    )
                    
                    tool_calls.append(ToolCall(
                        tool_name="filesystem",
                        parameters={
                            "action": "write_file",
                            "path": file_path,
                            "content": generated_code[:100] + ("..." if len(generated_code) > 100 else "")
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
        """Get system prompt for code generation.
        
        Returns:
            System prompt emphasizing multi-language support.
        """
        return """You are the Coder Agent for Aegis-CLI.

Your role is to generate high-quality code in ANY programming language based on requirements.

SUPPORTED LANGUAGES:
- Python, JavaScript, TypeScript, HTML, CSS
- Go, Rust, Java, C, C++, C#
- Ruby, PHP, Swift, Kotlin
- SQL, Shell scripts, and more

CODE QUALITY STANDARDS:

For Python:
- Use type hints (Python 3.11+ with | syntax)
- Include comprehensive docstrings (Google style)
- Follow PEP8 strictly

For JavaScript/TypeScript:
- Use modern ES6+ syntax
- Include JSDoc comments for functions
- Follow standard conventions

For HTML:
- Use semantic HTML5 tags
- Include accessibility attributes (ARIA, alt, role, etc.)
- Proper document structure

For CSS:
- Use modern CSS3 features
- Follow naming conventions (BEM or similar)
- Include comments for complex selectors

For all languages:
- Implement security best practices
- Add input validation where appropriate
- Include proper error handling
- Write clean, readable code
- Add comments for complex logic
- Use meaningful variable/function names

CRITICAL RULES:
1. ❌ DO NOT use tool calls
2. ❌ DO NOT try to save files
3. ❌ DO NOT use eval(), exec(), or dangerous functions
4. ❌ DO NOT hardcode secrets or credentials
5. ✅ ALWAYS return code in markdown code blocks
6. ✅ ALWAYS use the correct language tag (```python, ```javascript, ```html, etc.)
7. ✅ ALWAYS return ONLY code, no explanations before/after

OUTPUT FORMAT:
Return ONLY the code in a markdown code block. No text before or after.

Example for JavaScript:
```javascript
function calculateSum(a, b) {
    return a + b;
}
```

Example for HTML:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Example</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>
```

If you receive feedback from Tester or Critic:
- Address ALL issues before proceeding
- Explain your fixes in code comments
- Don't repeat the same mistakes
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["filesystem", "context"]
