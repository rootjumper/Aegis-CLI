# Full Trace Logging in Aegis-CLI

## Overview

Aegis-CLI now features **comprehensive trace logging** that captures every detail of agent interactions with LLMs, including:

- ✅ **Tool calls made by LLMs** - See exactly which tools the AI decides to use
- ✅ **Complete tool parameters** - View all arguments passed to each tool with JSON formatting
- ✅ **Tool IDs and metadata** - Track individual tool invocations
- ✅ **Agent prompts and responses** - Full conversation history
- ✅ **File operations** - Detailed logging of filesystem changes
- ✅ **Raw LLM output** - Complete response content from the model

## What's New

### Automatic Tool Call Extraction

The LLM logger now **automatically extracts tool calls** from PydanticAI responses. No changes needed to agent code - the logger intelligently extracts:

1. Tool names
2. Tool IDs
3. Complete parameter dictionaries
4. Tool types

### Enhanced Log Format

Log files now include detailed sections for each tool call:

```
TOOL CALLS (2):

  [1] Tool Call:
      Name: filesystem
      ID: call_abc123
      Parameters:
        {
            "action": "write_file",
            "path": "/tmp/example.py",
            "content": "def hello():\n    print('Hello, world!')"
        }

  [2] Tool Call:
      Name: shell
      ID: call_def456
      Parameters:
        {
            "command": "pytest tests/",
            "timeout": 30
        }
```

## Log File Location

All logs are stored in `.aegis/llm_logs/` with timestamped session files:

```
.aegis/llm_logs/
├── session_2026-02-18_08-57-30.log
├── session_2026-02-18_09-15-42.log
└── session_2026-02-18_10-03-21.log
```

## Log File Structure

Each session log contains:

### 1. Prompt Section
```
================================================================================
[1] PROMPT - CoderAgent → claude-3-5-sonnet
Time: 2026-02-18T08:57:30.389887
================================================================================

SYSTEM PROMPT:
You are the Coder Agent for Aegis-CLI...

TOOLS (3):
  [1] filesystem
      Type: string
      Description: File operations with comprehensive functionality
      Parameters: {...}
  
  [2] shell
      Type: string
  
  [3] python_tool
      Type: string

USER PROMPT (57 chars):
Generate a Python function to calculate fibonacci numbers
```

### 2. Response Section
```
--------------------------------------------------------------------------------
[1] RESPONSE - CoderAgent
Time: 2026-02-18T08:57:30.391786
Finish Reason: tool_calls
--------------------------------------------------------------------------------

TOOL CALLS (2):
  [1] Tool Call:
      Name: filesystem
      ID: call_abc123
      Parameters:
        {
            "action": "write_file",
            "path": "/tmp/fibonacci.py",
            "content": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)"
        }

RAW RESPONSE (42 chars):
I'll create the fibonacci function for you

EXTRACTED CONTENT (66 chars):
def fib(n):
    if n <= 1: return n
    return fib(n-1) + fib(n-2)
```

### 3. Tool Execution Section
```
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
TOOL CALL - CoderAgent → filesystem
Time: 2026-02-18T08:57:30.430978
Success: True
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Parameters:
  {
      "action": "write_file",
      "path": "/tmp/fibonacci.py",
      "content": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)"
  }

Result (38 chars):
{'success': True, 'bytes_written': 68}
```

## Verbose Console Output

When running agents with `verbose=True`, you'll see rich formatted output in the console:

```python
from aegis.agents.coder import CoderAgent

agent = CoderAgent(verbose=True)  # Enable verbose logging
```

This displays:
- Color-coded panels for prompts, responses, and tool calls
- Syntax-highlighted code previews
- Real-time tool execution status
- Parameter details in expandable sections

## Using the LLM Logger Directly

You can also use the logger directly in your own code:

```python
from aegis.core.llm_logger import LLMLogger

# Create logger
logger = LLMLogger(log_dir=".aegis/llm_logs", verbose=True)

# Log a prompt
interaction_id = logger.log_prompt(
    agent_name="MyAgent",
    prompt="Your prompt here",
    model="claude-3-5-sonnet",
    system_prompt="Optional system prompt",
    tools=["filesystem", "shell"]
)

# Log a response (tool calls are auto-extracted)
logger.log_response(
    interaction_id=interaction_id,
    agent_name="MyAgent",
    response=pydantic_ai_result,  # PydanticAI AgentRunResult
    extracted_content="Parsed content",
    finish_reason="stop"
)

# Log individual tool calls
logger.log_tool_call(
    agent_name="MyAgent",
    tool_name="filesystem",
    parameters={"action": "write_file", "path": "/tmp/test.py"},
    result={"success": True},
    success=True
)
```

## Benefits

### For Debugging
- **See exactly what the LLM decided to do** - No more guessing which tools were called
- **Inspect parameters** - Verify the LLM is passing correct arguments
- **Track execution flow** - Follow the complete chain of agent actions

### For Monitoring
- **Audit tool usage** - See all filesystem and shell operations
- **Performance analysis** - Measure response times and token usage
- **Quality assurance** - Review LLM decisions and reasoning

### For Development
- **Reproduce issues** - Complete interaction history for debugging
- **Test validation** - Verify tool calls match expectations
- **Documentation** - Auto-generated execution traces

## Technical Details

### Auto-Extraction Algorithm

The logger extracts tool calls from PydanticAI responses by:

1. Accessing `result.all_messages()` to get message history
2. Checking each message for `tool_calls` attribute
3. Extracting from each tool call:
   - Tool name (from `.name` or `.function.name`)
   - Tool ID (from `.id`)
   - Parameters (from `.arguments` - handles both dict and JSON string)
   - Tool type (if available)

### Backward Compatibility

The enhancement is **100% backward compatible**:
- Existing agent code works without changes
- Tool calls are extracted automatically
- Legacy log format still supported
- No breaking changes to API

### Performance

Tool call extraction is:
- **Fast** - Minimal overhead (<1ms per response)
- **Safe** - Gracefully handles malformed responses
- **Reliable** - Works with all PydanticAI-supported LLM providers

## Examples

### Example 1: Code Generation with Tools

```python
from aegis.agents.coder import CoderAgent
from aegis.agents.base import AgentTask

agent = CoderAgent(verbose=True)

task = AgentTask(
    id="task-001",
    type="code",
    payload={
        "description": "Create a calculator function",
        "file_path": "calculator.py"
    }
)

result = await agent.process(task)
```

**Log output shows:**
- Prompt sent to LLM
- Tool calls made (e.g., `filesystem.write_file`)
- Complete parameters (path, content)
- Execution results

### Example 2: Testing with Shell Execution

```python
from aegis.agents.tester import TesterAgent

agent = TesterAgent(verbose=True)

task = AgentTask(
    id="task-002", 
    type="test",
    payload={"code": "def add(a, b): return a + b"}
)

result = await agent.process(task)
```

**Log output shows:**
- Test generation prompt
- Tool calls for writing test files
- Shell tool execution (pytest)
- Test results and coverage

## Troubleshooting

### Q: I don't see tool calls in my logs

**A:** Make sure:
1. Your agent is actually using tools (check the agent's `get_required_tools()`)
2. The LLM is configured to use tools (not text-only mode)
3. You're looking at the correct log file (check `.aegis/llm_logs/`)

### Q: Parameters are showing as strings instead of JSON

**A:** This happens when:
- The LLM returns malformed JSON (logger logs it as-is)
- Tool uses custom parameter format (non-JSON)
- Check the `raw_response` section for the original LLM output

### Q: Logs are too verbose

**A:** You can:
1. Set `verbose=False` to disable console output
2. Only check log files when needed
3. Configure log retention to auto-delete old logs

## Related Documentation

- [LLM Configuration Guide](docs/LLM_CONFIGURATION.md)
- [Tool Development Guide](docs/TOOL_DEVELOPMENT.md)
- [Agent Architecture](README.md#agents)

## Summary

Full trace logging provides complete visibility into agent behavior, making it easier to:
- **Debug** LLM tool usage
- **Monitor** agent performance  
- **Audit** system operations
- **Develop** new features with confidence

The feature is automatic, performant, and backward compatible - just upgrade and start seeing detailed logs immediately!
