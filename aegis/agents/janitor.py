"""Janitor agent for documentation maintenance.

Keeps documentation in sync with code changes.
"""

from typing import Any
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, ToolCall
from aegis.tools.registry import get_registry
from aegis.core.llm_response_parser import LLMResponseParser


class JanitorAgent(BaseAgent):
    """Agent specialized in documentation maintenance.
    
    Responsibilities:
    - Update README.md with new features
    - Sync docstrings with code changes
    - Generate API documentation
    - Clean up unused imports
    """
    
    def __init__(self, model: Model | None = None) -> None:
        """Initialize the janitor agent.
        
        Args:
            model: Optional PydanticAI Model to use
        """
        super().__init__("janitor", model=model)
        self.registry = get_registry()
        self.parser = LLMResponseParser(strict=False)
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a documentation task using LLM.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with documentation results
        """
        from pydantic_ai import Agent as PydanticAgent
        from aegis.core.tool_bridge import create_toolset_from_registry
        
        try:
            # Get task details
            doc_type = task.payload.get("doc_type", "general")
            target_file = task.payload.get("target_file", "README.md")
            changes = task.payload.get("changes", [])
            
            # Get model and tools
            model = self.get_model()
            toolset = create_toolset_from_registry(self.registry)
            
            # Create PydanticAI agent
            pydantic_agent = PydanticAgent(
                model=model,
                tools=toolset,
                system_prompt=self.get_system_prompt()
            )
            
            tool_calls = []
            
            # Read current documentation if it exists
            fs_tool = self.registry.get_tool("filesystem")
            current_content = ""
            
            if fs_tool:
                read_result = await fs_tool.execute(
                    action="read_file",
                    path=target_file
                )
                
                if read_result.success:
                    current_content = read_result.data.get("content", "")
                    tool_calls.append(ToolCall(
                        tool_name="filesystem",
                        parameters={"action": "read_file", "path": target_file},
                        result=read_result.data,
                        success=True
                    ))
            
            # Build update prompt based on doc type
            if doc_type == "readme":
                update_prompt = f"""Update this README file with new information:

**Current README:**
```markdown
{current_content if current_content else "# New Project\n\nNo existing README."}
```

**Changes to document:**
{'\n'.join(f"- {c}" for c in changes)}

**Instructions:**
- Maintain existing structure and formatting
- Update relevant sections with new information
- Add new sections if needed
- Keep formatting consistent (markdown)
- Preserve all existing content unless it conflicts with updates

Return the complete updated README content."""

            elif doc_type == "docstring":
                update_prompt = f"""Update docstrings in Python code to match changes:

**Changes:**
{'\n'.join(f"- {c}" for c in changes)}

Generate updated docstrings in Google style format with:
- Brief description
- Args section
- Returns section
- Raises section (if applicable)

Return the updated docstring content."""

            else:  # general documentation
                update_prompt = f"""Update documentation for: {target_file}

**Current content:**
```
{current_content if current_content else "New file"}
```

**Changes:**
{'\n'.join(f"- {c}" for c in changes)}

Return the updated documentation."""
            
            # Generate updated documentation
            result = await pydantic_agent.run(update_prompt)
            
            # Extract updated content using universal parser
            # For documentation, use 'text' type to preserve markdown formatting
            updated_content = self.parser.parse(result, content_type='text')
            
            # Write updated documentation
            if fs_tool:
                write_result = await fs_tool.execute(
                    action="write_file",
                    path=target_file,
                    content=updated_content
                )
                
                tool_calls.append(ToolCall(
                    tool_name="filesystem",
                    parameters={
                        "action": "write_file",
                        "path": target_file,
                        "content": updated_content[:100] + ("..." if len(updated_content) > 100 else "")
                    },
                    result=write_result.data,
                    success=write_result.success,
                    error=write_result.error
                ))
            
            return AgentResponse(
                status="SUCCESS",
                data={"message": f"Updated {doc_type} documentation", "file": target_file},
                reasoning_trace=f"Documentation file {target_file} updated successfully",
                tool_calls=tool_calls
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error updating documentation: {e}",
                errors=[str(e)]
            )
    
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
