# Tool Usage Guide

This guide provides examples and best practices for using Aegis-CLI tools.

## Available Tools

Aegis-CLI includes 6 built-in tools:

1. **filesystem** - File system operations
2. **shell** - Safe command execution
3. **context** - Agent memory management
4. **git** - Git operations
5. **testing** - Test execution and reporting
6. **python** - Python code analysis

## Listing Available Tools

```bash
aegis tools
```

## FileSystem Tool

File operations including read, write, search, and modify.

### Actions

- `read_file` - Read file contents
- `write_file` - Write content to a file
- `delete_file` - Delete a file
- `create_directory` - Create a directory
- `list_directory` - List directory contents
- `search_content` - Search for patterns in files
- `smart_patch` - Apply surgical edits to files
- `file_exists` - Check if a file exists

### Examples

#### Read a File

```python
from aegis.tools.filesystem import FileSystemTool

tool = FileSystemTool()
result = await tool.execute(
    action="read_file",
    path="example.py"
)

if result.success:
    content = result.data
    print(content)
```

#### Write a File

```python
result = await tool.execute(
    action="write_file",
    path="output.txt",
    content="Hello, World!"
)
```

#### Search for Content

```python
result = await tool.execute(
    action="search_content",
    pattern="def.*:",  # Find function definitions
    path="./src"
)

if result.success:
    for match in result.data:
        print(f"{match['file']}:{match['line']}: {match['content']}")
```

#### Smart Patch

```python
result = await tool.execute(
    action="smart_patch",
    path="example.py",
    changes=[
        {
            "action": "replace",
            "old": "old_function_name",
            "new": "new_function_name"
        }
    ]
)
```

## Shell Tool

Execute commands safely with whitelist enforcement.

### Whitelisted Commands

- Development: `python`, `pip`, `npm`, `node`, `yarn`
- Version Control: `git`
- Testing: `pytest`, `mypy`, `pylint`
- Formatting: `black`, `ruff`, `prettier`, `eslint`
- Utilities: `ls`, `cat`, `grep`, `find`, `echo`, `pwd`
- Containers: `docker`, `kubectl`
- And more...

### Examples

#### Run Tests

```python
from aegis.tools.shell import SafeShell

tool = SafeShell()
result = await tool.execute(
    command=["pytest", "tests/", "-v"],
    require_confirmation=False
)

if result.success:
    print(result.data["stdout"])
```

#### Execute Git Command

```python
result = await tool.execute(
    command=["git", "status", "--short"],
    require_confirmation=False
)
```

#### Run with Timeout

```python
result = await tool.execute(
    command=["python", "script.py"],
    require_confirmation=False,
    timeout=60  # 60 seconds
)
```

## Context Tool

Manage agent memory and context.

### Actions

- `remember` - Store a value
- `recall` - Retrieve a value
- `forget` - Delete a value

### Examples

#### Store Information

```python
from aegis.tools.context import ContextTool

tool = ContextTool()
result = await tool.execute(
    action="remember",
    key="project_info",
    value={"name": "MyProject", "version": "1.0"},
    agent="coder",
    ttl=3600  # Expires in 1 hour
)
```

#### Retrieve Information

```python
result = await tool.execute(
    action="recall",
    key="project_info"
)

if result.success:
    project_info = result.data
    print(project_info)
```

#### Delete Information

```python
result = await tool.execute(
    action="forget",
    key="project_info"
)
```

## Git Tool

Git operations for version control.

### Actions

- `status` - Get repository status
- `diff` - Show differences
- `log` - View commit history
- `branch` - List or create branches
- `show` - Show commit details
- `list_branches` - List all branches
- `current_branch` - Get current branch
- `add` - Stage files
- `commit` - Create a commit

### Examples

#### Check Status

```python
from aegis.tools.git import GitTool

tool = GitTool()
result = await tool.execute(action="status")

if result.success:
    status = result.data["summary"]
    print(f"Modified: {len(status['modified'])}")
    print(f"Untracked: {len(status['untracked'])}")
```

#### View Commit History

```python
result = await tool.execute(
    action="log",
    limit=10
)

if result.success:
    for commit in result.data["commits"]:
        print(f"{commit['hash'][:7]} - {commit['message']}")
```

#### Get Diff

```python
result = await tool.execute(
    action="diff",
    path="example.py",
    staged=False
)

if result.success:
    print(result.data["diff"])
```

## Testing Tool

Test execution and analysis.

### Actions

- `run_tests` - Run pytest tests
- `run_coverage` - Run tests with coverage
- `list_tests` - List available tests
- `run_specific` - Run specific test
- `validate_tests` - Validate test structure

### Examples

#### Run Tests

```python
from aegis.tools.testing import TestingTool

tool = TestingTool()
result = await tool.execute(
    action="run_tests",
    path="tests/",
    verbose=True
)

if result.success:
    summary = result.data["summary"]
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
```

#### Run Coverage Analysis

```python
result = await tool.execute(
    action="run_coverage",
    path="tests/",
    coverage_threshold=80
)

if result.success:
    coverage = result.data["coverage_percentage"]
    print(f"Coverage: {coverage}%")
```

#### List Tests

```python
result = await tool.execute(
    action="list_tests",
    path="tests/"
)

if result.success:
    for test in result.data["tests"]:
        print(test)
```

## Python Tool

Python code analysis and operations.

### Actions

- `analyze_imports` - Analyze import statements
- `lint` - Run pylint
- `type_check` - Run mypy type checking
- `format_check` - Check code formatting
- `parse_syntax` - Validate Python syntax
- `get_functions` - Extract function definitions
- `get_classes` - Extract class definitions

### Examples

#### Analyze Imports

```python
from aegis.tools.python import PythonTool

tool = PythonTool()
result = await tool.execute(
    action="analyze_imports",
    path="example.py"
)

if result.success:
    imports = result.data["imports"]
    print(f"Third-party: {imports['third_party']}")
    print(f"From imports: {len(imports['from_imports'])}")
```

#### Run Type Checking

```python
result = await tool.execute(
    action="type_check",
    path="src/"
)

if result.success and result.data["passed"]:
    print("Type checking passed!")
else:
    for error in result.data["errors"]:
        print(error)
```

#### Extract Functions

```python
result = await tool.execute(
    action="get_functions",
    path="example.py"
)

if result.success:
    for func in result.data["functions"]:
        print(f"{func['name']}({', '.join(func['arguments'])})")
        if func["docstring"]:
            print(f"  {func['docstring']}")
```

#### Extract Classes

```python
result = await tool.execute(
    action="get_classes",
    path="example.py"
)

if result.success:
    for cls in result.data["classes"]:
        print(f"class {cls['name']}:")
        for method in cls["methods"]:
            print(f"  - {method}()")
```

## Error Handling

All tools return a `ToolResult` object with:

- `success` (bool): Whether the operation succeeded
- `data` (Any): Result data if successful
- `error` (str | None): Error message if failed

### Example Error Handling

```python
result = await tool.execute(action="read_file", path="nonexistent.txt")

if result.success:
    print(result.data)
else:
    print(f"Error: {result.error}")
```

## CLI Integration

Tools are automatically available to agents when running tasks:

```bash
aegis run "Read the README file and summarize it"
```

The agents will automatically use the appropriate tools to complete the task.

## Tips and Best Practices

1. **Check Success**: Always check `result.success` before using data
2. **Error Messages**: Read error messages carefully for debugging
3. **Type Hints**: Use type hints for better IDE support
4. **Async/Await**: Remember all tool operations are async
5. **Resource Management**: Tools handle cleanup automatically
6. **Security**: Tools enforce security constraints (e.g., command whitelist)

## Advanced Usage

### Chaining Tools

```python
# Read file
read_result = await filesystem_tool.execute(
    action="read_file",
    path="example.py"
)

if read_result.success:
    # Analyze the code
    analysis_result = await python_tool.execute(
        action="get_functions",
        path="example.py"
    )
    
    if analysis_result.success:
        # Store in context
        await context_tool.execute(
            action="remember",
            key="code_analysis",
            value=analysis_result.data,
            agent="analyzer"
        )
```

### Custom Tool Sequences

Create reusable sequences:

```python
async def analyze_and_test(file_path: str):
    """Analyze a Python file and run its tests."""
    
    # Parse syntax
    syntax_result = await python_tool.execute(
        action="parse_syntax",
        path=file_path
    )
    
    if not syntax_result.success:
        return syntax_result
    
    # Run tests
    test_result = await testing_tool.execute(
        action="run_tests",
        path=f"tests/test_{Path(file_path).name}"
    )
    
    return test_result
```

## Troubleshooting

### Tool Not Found

```bash
# List available tools
aegis tools

# Check registry
python -c "from aegis.tools.registry import get_registry; print(get_registry().list_available_tools())"
```

### Permission Denied

Ensure files and directories have appropriate permissions:

```bash
chmod +r file.txt  # Make readable
chmod +w file.txt  # Make writable
```

### Command Not Whitelisted

For shell tool, check if command is in whitelist:

```python
from aegis.tools.shell import SafeShell
print(SafeShell.SAFE_COMMANDS)
```

## Getting Help

- Check the [Tool Development Guide](TOOL_DEVELOPMENT.md)
- View source code in `aegis/tools/`
- Run `aegis doctor` for health checks
- Run `aegis validate` for configuration validation
