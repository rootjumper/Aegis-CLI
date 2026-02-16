# Tool Development Guide

This guide explains how to develop new tools for Aegis-CLI.

## Overview

Tools in Aegis-CLI provide capabilities to agents. Each tool implements a specific interface and can be automatically discovered and registered by the tool registry.

## Tool Structure

All tools must inherit from the `Tool` abstract base class defined in `aegis/tools/base_tool.py`.

### Required Components

1. **name** (property): Unique identifier for the tool
2. **description** (property): Human-readable description
3. **parameters_schema** (property): JSON schema for parameters
4. **execute** (method): Async method that performs the tool's action

## Creating a New Tool

### 1. Create the Tool Class

Create a new file in `aegis/tools/` with your tool implementation:

```python
"""My custom tool for Aegis-CLI."""

from typing import Any
from aegis.tools.base_tool import Tool, ToolResult


class MyCustomTool(Tool):
    """Tool for custom operations."""
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "custom"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "Perform custom operations"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["action1", "action2"],
                    "description": "Action to perform"
                },
                "param1": {
                    "type": "string",
                    "description": "First parameter"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the custom operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult containing operation results
        """
        action = kwargs.get("action")
        
        try:
            if action == "action1":
                return await self._action1(kwargs)
            elif action == "action2":
                return await self._action2(kwargs)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _action1(self, params: dict[str, Any]) -> ToolResult:
        """Implement action 1."""
        # Your implementation here
        return ToolResult(success=True, data={"message": "Action 1 complete"})
    
    async def _action2(self, params: dict[str, Any]) -> ToolResult:
        """Implement action 2."""
        # Your implementation here
        return ToolResult(success=True, data={"message": "Action 2 complete"})
```

### 2. Register the Tool

Add your tool module to the registry in `aegis/tools/registry.py`:

```python
tool_modules = [
    "aegis.tools.filesystem",
    "aegis.tools.shell",
    "aegis.tools.context",
    "aegis.tools.git",
    "aegis.tools.testing",
    "aegis.tools.python",
    "aegis.tools.custom"  # Add your tool here
]
```

### 3. Write Tests

Create tests for your tool in `tests/test_custom_tool.py`:

```python
"""Tests for custom tool."""

import pytest
from aegis.tools.custom import MyCustomTool


@pytest.fixture
def custom_tool():
    """Create a MyCustomTool instance."""
    return MyCustomTool()


def test_custom_tool_creation(custom_tool):
    """Test creating a custom tool."""
    assert custom_tool.name == "custom"
    assert "custom" in custom_tool.description.lower()


def test_custom_tool_schema(custom_tool):
    """Test custom tool parameter schema."""
    schema = custom_tool.parameters_schema
    
    assert "properties" in schema
    assert "action" in schema["properties"]
    assert schema["required"] == ["action"]


@pytest.mark.asyncio
async def test_action1(custom_tool):
    """Test action1."""
    result = await custom_tool.execute(
        action="action1",
        param1="test"
    )
    
    assert result.success is True
    assert result.data is not None


@pytest.mark.asyncio
async def test_invalid_action(custom_tool):
    """Test invalid action."""
    result = await custom_tool.execute(action="invalid")
    
    assert result.success is False
    assert "Unknown action" in result.error
```

## Best Practices

### 1. Error Handling

Always wrap operations in try-except blocks and return appropriate ToolResult:

```python
try:
    # Your operation
    return ToolResult(success=True, data=result)
except Exception as e:
    return ToolResult(success=False, error=str(e))
```

### 2. Parameter Validation

Use the JSON schema to validate required parameters:

```python
if not params.get("required_param"):
    return ToolResult(success=False, error="Required parameter missing")
```

### 3. Async Operations

All execute methods must be async. For synchronous operations, use:

```python
async def execute(self, **kwargs: Any) -> ToolResult:
    # Sync operation wrapped in async
    result = self._sync_operation(kwargs)
    return ToolResult(success=True, data=result)
```

### 4. Type Hints

Use proper type hints for all methods:

```python
async def execute(self, **kwargs: Any) -> ToolResult:
    """Execute with type hints."""
    pass
```

### 5. Docstrings

Provide clear docstrings for the class and all methods:

```python
class MyTool(Tool):
    """Tool for specific operations.
    
    Provides capabilities for X, Y, and Z.
    """
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with operation results
        """
        pass
```

## Tool Categories

### File Operations

Tools that work with the filesystem (read, write, search).

**Example**: `FileSystemTool`

### Command Execution

Tools that execute commands or external programs.

**Example**: `SafeShell`, `TestingTool`

### Data Analysis

Tools that analyze or process data.

**Example**: `PythonTool`, `GitTool`

### Context Management

Tools that manage state or memory.

**Example**: `ContextTool`

## Testing Your Tool

Run the tests:

```bash
# Test specific tool
pytest tests/test_custom_tool.py -v

# Test all tools
pytest tests/ -k tool -v

# With coverage
pytest tests/test_custom_tool.py --cov=aegis.tools.custom
```

## Common Patterns

### Pattern 1: Action-Based Tool

Use an action parameter to route to different operations:

```python
async def execute(self, **kwargs: Any) -> ToolResult:
    action = kwargs.get("action")
    
    if action == "read":
        return await self._read(kwargs)
    elif action == "write":
        return await self._write(kwargs)
    # ...
```

### Pattern 2: File Processing

Handle file operations safely:

```python
async def _process_file(self, path: str) -> ToolResult:
    if not os.path.exists(path):
        return ToolResult(success=False, error=f"File not found: {path}")
    
    try:
        with open(path, "r") as f:
            content = f.read()
        # Process content
        return ToolResult(success=True, data=result)
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

### Pattern 3: Command Execution

Execute external commands safely:

```python
async def _run_command(self, args: list[str]) -> ToolResult:
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        success = process.returncode == 0
        
        return ToolResult(
            success=success,
            data={"stdout": stdout.decode(), "stderr": stderr.decode()}
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))
```

## Security Considerations

1. **Input Validation**: Always validate user input
2. **Path Traversal**: Check for `..` in file paths
3. **Command Injection**: Use parameterized commands
4. **Resource Limits**: Set timeouts for operations
5. **Error Messages**: Don't expose sensitive information

## Debugging

Enable verbose output:

```bash
aegis run "Task" --verbose
```

Check logs:

```bash
ls -la .aegis/logs/
cat .aegis/logs/task-*.md
```

## Examples

See existing tools for reference:

- **FileSystemTool**: File operations with multiple actions
- **GitTool**: Command execution with output parsing
- **PythonTool**: Code analysis with AST
- **TestingTool**: Test execution and reporting

## Resources

- [Tool Base Class](../aegis/tools/base_tool.py)
- [Tool Registry](../aegis/tools/registry.py)
- [Existing Tools](../aegis/tools/)
- [Test Examples](../tests/)
