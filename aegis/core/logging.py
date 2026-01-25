"""Logging system for Aegis-CLI with Markdown trace writer.

This module provides structured logging with both file-based markdown traces
and rich console output.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.live import Live
from rich.table import Table


class LogLevel(str, Enum):
    """Log levels for the Aegis logging system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    THOUGHT = "THOUGHT"
    ACTION = "ACTION"
    RESULT = "RESULT"
    ERROR = "ERROR"


class TraceLogger:
    """Markdown-based reasoning trace logger.
    
    Creates timestamped log files in the .aegis/logs directory and provides
    rich console output for real-time feedback.
    """
    
    def __init__(
        self,
        task_id: str,
        task_name: str = "task",
        logs_path: str = ".aegis/logs"
    ) -> None:
        """Initialize the trace logger.
        
        Args:
            task_id: Unique task identifier
            task_name: Human-readable task name
            logs_path: Directory for log files
        """
        self.task_id = task_id
        self.task_name = task_name
        self.logs_path = Path(logs_path)
        self.console = Console()
        
        # Ensure logs directory exists
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_name)
        self.log_file = self.logs_path / f"{timestamp}_{safe_name}.md"
        
        # Initialize log file
        self._init_log_file()
    
    def _init_log_file(self) -> None:
        """Initialize the markdown log file with header."""
        header = f"""# Task Execution Log: {self.task_name}

**Task ID:** `{self.task_id}`  
**Started:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(header)
    
    def _append_to_file(self, content: str) -> None:
        """Append content to the log file.
        
        Args:
            content: Content to append
        """
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content + "\n\n")
    
    def log(
        self,
        level: LogLevel,
        message: str,
        agent: str | None = None,
        code: str | None = None,
        code_language: str = "python"
    ) -> None:
        """Log a message with specified level.
        
        Args:
            level: Log level
            message: Message to log
            agent: Optional agent name
            code: Optional code block
            code_language: Language for code highlighting
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Build markdown content
        md_content = f"## [{timestamp}] {level.value}"
        if agent:
            md_content += f" - *{agent}*"
        md_content += f"\n\n{message}"
        
        if code:
            md_content += f"\n\n```{code_language}\n{code}\n```"
        
        # Write to file
        self._append_to_file(md_content)
        
        # Console output
        self._console_output(level, message, agent, code, code_language)
    
    def _console_output(
        self,
        level: LogLevel,
        message: str,
        agent: str | None,
        code: str | None,
        code_language: str
    ) -> None:
        """Output to console with rich formatting.
        
        Args:
            level: Log level
            message: Message to log
            agent: Optional agent name
            code: Optional code block
            code_language: Language for code highlighting
        """
        # Choose color based on level
        color_map = {
            LogLevel.DEBUG: "dim",
            LogLevel.INFO: "cyan",
            LogLevel.THOUGHT: "yellow",
            LogLevel.ACTION: "green",
            LogLevel.RESULT: "blue",
            LogLevel.ERROR: "red"
        }
        color = color_map.get(level, "white")
        
        # Build title
        title = level.value
        if agent:
            title += f" - {agent}"
        
        # Create panel
        if code:
            syntax = Syntax(code, code_language, theme="monokai", line_numbers=True)
            self.console.print(Panel(
                f"{message}\n\n{syntax}",
                title=title,
                border_style=color
            ))
        else:
            self.console.print(Panel(
                message,
                title=title,
                border_style=color
            ))
    
    def log_agent_thought(self, agent: str, thought: str) -> None:
        """Log an agent's thought process.
        
        Args:
            agent: Agent name
            thought: Thought content
        """
        self.log(LogLevel.THOUGHT, thought, agent=agent)
    
    def log_tool_call(
        self,
        tool: str,
        params: dict[str, Any],
        result: Any = None
    ) -> None:
        """Log a tool call.
        
        Args:
            tool: Tool name
            params: Tool parameters
            result: Tool result
        """
        message = f"**Tool:** `{tool}`\n\n**Parameters:**\n```json\n{params}\n```"
        
        if result is not None:
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "... (truncated)"
            message += f"\n\n**Result:**\n```\n{result_str}\n```"
        
        self.log(LogLevel.ACTION, message)
    
    def log_error(
        self,
        error: str,
        agent: str | None = None,
        traceback: str | None = None
    ) -> None:
        """Log an error.
        
        Args:
            error: Error message
            agent: Optional agent name
            traceback: Optional traceback
        """
        message = error
        code = traceback if traceback else None
        self.log(LogLevel.ERROR, message, agent=agent, code=code, code_language="text")
    
    def log_info(self, message: str, agent: str | None = None) -> None:
        """Log an informational message.
        
        Args:
            message: Message to log
            agent: Optional agent name
        """
        self.log(LogLevel.INFO, message, agent=agent)
    
    def log_debug(self, message: str, agent: str | None = None) -> None:
        """Log a debug message.
        
        Args:
            message: Message to log
            agent: Optional agent name
        """
        self.log(LogLevel.DEBUG, message, agent=agent)
    
    def log_result(self, message: str, agent: str | None = None) -> None:
        """Log a result.
        
        Args:
            message: Message to log
            agent: Optional agent name
        """
        self.log(LogLevel.RESULT, message, agent=agent)
    
    def finalize(self, success: bool = True) -> None:
        """Finalize the log file.
        
        Args:
            success: Whether the task succeeded
        """
        footer = f"""---

## Summary

**Completed:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Status:** {"✅ SUCCESS" if success else "❌ FAILED"}
"""
        self._append_to_file(footer)
        
        # Console output
        status_text = "[green]SUCCESS[/green]" if success else "[red]FAILED[/red]"
        self.console.print(f"\n[bold]Task {status_text}[/bold]")
        self.console.print(f"[dim]Log file: {self.log_file}[/dim]\n")


def create_trace_logger(
    task_id: str,
    task_name: str = "task",
    logs_path: str = ".aegis/logs"
) -> TraceLogger:
    """Create a new trace logger.
    
    Args:
        task_id: Unique task identifier
        task_name: Human-readable task name
        logs_path: Directory for log files
        
    Returns:
        TraceLogger instance
    """
    return TraceLogger(task_id, task_name, logs_path)
