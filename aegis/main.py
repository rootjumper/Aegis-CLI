"""Main CLI application for Aegis-CLI.

Provides the command-line interface for interacting with the agent system.
"""

import os
import asyncio
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from dotenv import load_dotenv

from aegis.agents.base import AgentTask
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.coder import CoderAgent
from aegis.agents.critic import CriticAgent
from aegis.agents.tester import TesterAgent
from aegis.agents.janitor import JanitorAgent
from aegis.core.state import get_state_manager
from aegis.core.logging import create_trace_logger
from aegis.core.verification import VerificationCycle
from aegis.tools.registry import get_registry

# Load environment variables
load_dotenv()

# Create Typer app
app = typer.Typer(
    name="aegis",
    help="Aegis-CLI: A modular, self-correcting multi-agent framework",
    add_completion=False
)

console = Console()


@app.command()
def run(
    prompt: str = typer.Argument(..., help="Task prompt for the agents"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    no_verify: bool = typer.Option(False, "--no-verify", help="Skip verification cycle")
) -> None:
    """Execute a task with the agent team."""
    asyncio.run(_run_task(prompt, verbose, no_verify))


async def _run_task(prompt: str, verbose: bool, no_verify: bool) -> None:
    """Run a task asynchronously.
    
    Args:
        prompt: User prompt
        verbose: Enable verbose output
        no_verify: Skip verification cycle
    """
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Create logger
    logger = create_trace_logger(task_id, "user-task")
    
    logger.log_info(f"Starting task: {prompt}")
    
    try:
        # Initialize state manager
        state_manager = get_state_manager()
        await state_manager.init_database()
        
        # Store task
        await state_manager.store_task(
            task_id=task_id,
            task_type="user_prompt",
            payload={"prompt": prompt},
            status="RUNNING"
        )
        
        # Create task
        task = AgentTask(
            id=task_id,
            type="user_prompt",
            payload={"prompt": prompt},
            context={}
        )
        
        # Initialize orchestrator
        orchestrator = OrchestratorAgent()
        
        # Process task
        logger.log_agent_thought("Orchestrator", "Analyzing prompt and decomposing into tasks")
        response = await orchestrator.process(task)
        
        logger.log_result(f"Status: {response.status}")
        logger.log_result(f"Reasoning: {response.reasoning_trace}")
        
        if response.status == "SUCCESS":
            subtasks = response.data.get("subtasks", [])
            logger.log_info(f"Decomposed into {len(subtasks)} subtasks")
            
            for i, subtask in enumerate(subtasks, 1):
                console.print(f"\n[cyan]Subtask {i}:[/cyan] {subtask.get('description', '')}")
            
            # Update task status
            await state_manager.update_task_status(task_id, "SUCCESS", completed=True)
            await state_manager.store_reasoning(task_id, "orchestrator", response.reasoning_trace)
            
            logger.finalize(success=True)
            console.print("\n[green]✓ Task completed successfully![/green]\n")
        else:
            # Update task status
            await state_manager.update_task_status(task_id, "FAILED", completed=True)
            
            logger.log_error(f"Task failed: {', '.join(response.errors)}")
            logger.finalize(success=False)
            console.print(f"\n[red]✗ Task failed: {', '.join(response.errors)}[/red]\n")
        
        # Close state manager
        await state_manager.close()
    
    except Exception as e:
        logger.log_error(f"Unexpected error: {e}")
        logger.finalize(success=False)
        console.print(f"\n[red]✗ Error: {e}[/red]\n")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show current session status."""
    asyncio.run(_show_status())


async def _show_status() -> None:
    """Show status asynchronously."""
    state_manager = get_state_manager()
    await state_manager.init_database()
    
    history = await state_manager.get_task_history(limit=10)
    
    if not history:
        console.print("[yellow]No tasks in history.[/yellow]")
        await state_manager.close()
        return
    
    # Create table
    table = Table(title="Recent Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Created", style="blue")
    
    for task in history:
        task_id_short = task["id"][:8]
        status_color = "green" if task["status"] == "SUCCESS" else "red"
        table.add_row(
            task_id_short,
            task["type"],
            f"[{status_color}]{task['status']}[/{status_color}]",
            task["created_at"] or "N/A"
        )
    
    console.print(table)
    await state_manager.close()


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of tasks to show")
) -> None:
    """Display task history."""
    asyncio.run(_show_history(limit))


async def _show_history(limit: int) -> None:
    """Show history asynchronously.
    
    Args:
        limit: Number of tasks to show
    """
    state_manager = get_state_manager()
    await state_manager.init_database()
    
    history = await state_manager.get_task_history(limit=limit)
    
    if not history:
        console.print("[yellow]No tasks in history.[/yellow]")
        await state_manager.close()
        return
    
    for task in history:
        panel_content = f"""
**Type:** {task['type']}
**Status:** {task['status']}
**Created:** {task['created_at']}
**Completed:** {task['completed_at'] or 'N/A'}
"""
        console.print(Panel(
            panel_content,
            title=f"Task {task['id'][:8]}",
            border_style="cyan"
        ))
    
    await state_manager.close()


@app.command()
def reset() -> None:
    """Clear session database and logs."""
    if typer.confirm("Are you sure you want to reset the session?"):
        asyncio.run(_reset_session())


async def _reset_session() -> None:
    """Reset session asynchronously."""
    # Delete database
    db_path = Path(".aegis/session.db")
    if db_path.exists():
        db_path.unlink()
        console.print("[green]✓ Database cleared[/green]")
    
    # Clear logs
    logs_path = Path(".aegis/logs")
    if logs_path.exists():
        for log_file in logs_path.glob("*.md"):
            log_file.unlink()
        console.print("[green]✓ Logs cleared[/green]")
    
    console.print("\n[bold green]Session reset complete![/bold green]\n")


@app.command()
def agents() -> None:
    """List available agents."""
    table = Table(title="Available Agents")
    table.add_column("Agent", style="cyan")
    table.add_column("Description", style="white")
    
    agents_info = [
        ("Orchestrator", "Task decomposition and delegation"),
        ("Coder", "Code generation with best practices"),
        ("Critic", "Code review and quality checks"),
        ("Tester", "Test generation and execution"),
        ("Janitor", "Documentation maintenance")
    ]
    
    for name, description in agents_info:
        table.add_row(name, description)
    
    console.print(table)


@app.command()
def tools() -> None:
    """List available tools."""
    registry = get_registry()
    tool_names = registry.list_available_tools()
    
    table = Table(title="Available Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Description", style="white")
    
    for tool_name in tool_names:
        tool = registry.get_tool(tool_name)
        if tool:
            table.add_row(tool_name, tool.description)
    
    console.print(table)


@app.callback()
def callback() -> None:
    """Aegis-CLI: A modular, self-correcting multi-agent framework."""
    pass


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
