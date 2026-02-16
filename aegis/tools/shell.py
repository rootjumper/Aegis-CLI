"""Safe shell execution tool for Aegis-CLI.

Provides command execution with whitelisting and human-in-the-loop confirmation.
"""

import asyncio
import subprocess
from typing import Any

from rich.console import Console
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.panel import Panel

from aegis.tools.base_tool import Tool, ToolResult


class SafeShell(Tool):
    """Safe shell command execution tool.
    
    Provides command execution with:
    - Whitelisted commands
    - Human-in-the-loop confirmation
    - Timeout enforcement
    - Output capture
    """
    
    # Whitelist of safe commands
    SAFE_COMMANDS = [
        "git", "pytest", "pip", "uv", "mypy", "pylint",
        "python", "python3", "ls", "cat", "grep", "find",
        "echo", "pwd", "which", "env", "black", "ruff",
        "npm", "node", "yarn", "pnpm", "make", "cmake",
        "cargo", "go", "rustc", "tsc", "eslint", "prettier",
        "docker", "kubectl", "terraform", "ansible"
    ]
    
    def __init__(self) -> None:
        """Initialize the safe shell tool."""
        super().__init__()
        self.console = Console()
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "shell"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "Execute shell commands safely with whitelist and confirmation"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command and arguments as list"
                },
                "require_confirmation": {
                    "type": "boolean",
                    "description": "Require human confirmation",
                    "default": True
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds",
                    "default": 30
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a shell command.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with command output
        """
        command = kwargs.get("command", [])
        require_confirmation = kwargs.get("require_confirmation", True)
        timeout = kwargs.get("timeout", 30)
        cwd = kwargs.get("cwd", None)
        
        if not command:
            return ToolResult(success=False, error="Command is required")
        
        # Validate command is in whitelist
        base_command = command[0]
        if base_command not in self.SAFE_COMMANDS:
            return ToolResult(
                success=False,
                error=f"Command '{base_command}' is not whitelisted. "
                      f"Safe commands: {', '.join(self.SAFE_COMMANDS)}"
            )
        
        # Show command preview
        cmd_str = " ".join(command)
        self._show_command_preview(cmd_str)
        
        # Request confirmation if required
        if require_confirmation:
            if not Confirm.ask(f"[yellow]Execute this command?[/yellow]"):
                return ToolResult(
                    success=False,
                    error="Command execution cancelled by user"
                )
        
        # Execute command
        try:
            result = await self._run_command(command, timeout, cwd)
            return result
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _show_command_preview(self, command: str) -> None:
        """Show command preview with syntax highlighting.
        
        Args:
            command: Command string
        """
        syntax = Syntax(command, "bash", theme="monokai")
        self.console.print(Panel(
            syntax,
            title="[bold]Command Preview[/bold]",
            border_style="yellow"
        ))
    
    async def _run_command(
        self,
        command: list[str],
        timeout: int,
        cwd: str | None
    ) -> ToolResult:
        """Run the command and capture output.
        
        Args:
            command: Command and arguments
            timeout: Timeout in seconds
            cwd: Working directory
            
        Returns:
            ToolResult with output
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            # Wait with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {timeout} seconds"
                )
            
            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            # Check return code
            success = process.returncode == 0
            
            result_data = {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "returncode": process.returncode
            }
            
            # Display output
            if stdout_str:
                self.console.print("[dim]stdout:[/dim]")
                self.console.print(stdout_str)
            if stderr_str:
                self.console.print("[dim]stderr:[/dim]")
                self.console.print(f"[red]{stderr_str}[/red]")
            
            if not success:
                return ToolResult(
                    success=False,
                    data=result_data,
                    error=f"Command failed with return code {process.returncode}"
                )
            
            return ToolResult(success=True, data=result_data)
        
        except Exception as e:
            return ToolResult(success=False, error=f"Error executing command: {e}")


# Convenience function for direct execution
async def execute_command(
    command: list[str],
    require_confirmation: bool = True,
    timeout: int = 30,
    cwd: str | None = None
) -> ToolResult:
    """Execute a shell command using SafeShell.
    
    Args:
        command: Command and arguments
        require_confirmation: Require human confirmation
        timeout: Timeout in seconds
        cwd: Working directory
        
    Returns:
        ToolResult with output
    """
    shell = SafeShell()
    return await shell.execute(
        command=command,
        require_confirmation=require_confirmation,
        timeout=timeout,
        cwd=cwd
    )
