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

# Configuration constants
DEFAULT_TASK_TIMEOUT = 300  # 5 minutes per task
DEFAULT_VERIFICATION_TIMEOUT = 600  # 10 minutes for verification cycle

# Create Typer app
app = typer.Typer(
    name="aegis",
    help="Aegis-CLI: A modular, self-correcting multi-agent framework",
    add_completion=False
)

console = Console()


async def _execute_subtasks(
    subtasks: list[dict],
    task_id: str,
    logger,
    state_manager,
    no_verify: bool
) -> bool:
    """Execute subtasks by delegating to appropriate agents.
    
    Args:
        subtasks: List of subtask dictionaries
        task_id: Parent task ID
        logger: Trace logger
        state_manager: State manager instance
        no_verify: Whether to skip verification cycle
        
    Returns:
        True if all subtasks succeeded, False otherwise
    """
    overall_success = True
    
    for i, subtask_dict in enumerate(subtasks, 1):
        subtask_type = subtask_dict.get("type", "code")
        description = subtask_dict.get("description", "")
        priority = subtask_dict.get("priority", 1)
        
        console.print(f"\n[bold cyan]Executing subtask {i}/{len(subtasks)}:[/bold cyan] {description}")
        logger.log_info(f"Processing subtask {i}: {subtask_type}", agent="Orchestrator")
        
        # Create subtask
        subtask = AgentTask(
            id=f"{task_id}_subtask_{i}",
            type=subtask_type,
            payload={
                "description": description,
                "priority": priority
            },
            context={}
        )
        
        # Store subtask
        await state_manager.store_task(
            task_id=subtask.id,
            task_type=subtask_type,
            payload=subtask.payload,
            status="RUNNING"
        )
        
        try:
            # Determine which agent to use and whether to use verification cycle
            success = await _execute_single_subtask(
                subtask, 
                subtask_type, 
                logger, 
                state_manager,
                no_verify
            )
            
            if success:
                await state_manager.update_task_status(subtask.id, "SUCCESS", completed=True)
                console.print(f"[green]✓ Subtask {i} completed[/green]")
            else:
                await state_manager.update_task_status(subtask.id, "FAILED", completed=True)
                console.print(f"[red]✗ Subtask {i} failed[/red]")
                overall_success = False
        
        except Exception as e:
            logger.log_error(f"Error executing subtask {i}: {e}", agent="Orchestrator")
            await state_manager.update_task_status(subtask.id, "FAILED", completed=True)
            console.print(f"[red]✗ Subtask {i} failed: {e}[/red]")
            overall_success = False
    
    return overall_success


async def _execute_single_subtask(
    task: AgentTask,
    task_type: str,
    logger,
    state_manager,
    no_verify: bool
) -> bool:
    """Execute a single subtask with appropriate agent.
    
    Args:
        task: Task to execute
        task_type: Type of task
        logger: Trace logger
        state_manager: State manager instance
        no_verify: Whether to skip verification cycle
        
    Returns:
        True if task succeeded, False otherwise
    """
    # For code and test tasks, use verification cycle unless disabled
    if task_type in ["code", "test"] and not no_verify:
        return await _execute_with_verification(task, logger, state_manager)
    
    # For other tasks or when verification is disabled, execute directly
    return await _execute_with_agent(task, task_type, logger, state_manager)


async def _execute_with_verification(
    task: AgentTask,
    logger,
    state_manager
) -> bool:
    """Execute task through verification cycle.
    
    Args:
        task: Task to execute
        logger: Trace logger
        state_manager: State manager instance
        
    Returns:
        True if verification succeeded, False otherwise
    """
    from aegis.core.llm_config import get_default_model
    
    logger.log_info("Starting verification cycle", agent="VerificationCycle")
    
    # Get default model
    model = get_default_model()
    
    # Initialize agents for verification cycle with model
    coder = CoderAgent(model=model)
    tester = TesterAgent(model=model)
    critic = CriticAgent(model=model)
    
    # Create verification cycle
    verification = VerificationCycle(
        coder=coder,
        tester=tester,
        critic=critic,
        logger=logger
    )
    
    try:
        # Run verification cycle with timeout
        response = await asyncio.wait_for(
            verification.run(task),
            timeout=DEFAULT_VERIFICATION_TIMEOUT
        )
        
        # Store reasoning
        await state_manager.store_reasoning(
            task.id,
            "verification_cycle",
            response.reasoning_trace
        )
        
        # Log tool calls
        for tool_call in response.tool_calls:
            logger.log_info(
                f"Tool call: {tool_call.tool_name}",
                agent="VerificationCycle"
            )
        
        return response.status == "SUCCESS"
    
    except asyncio.TimeoutError:
        logger.log_error(
            f"Verification cycle timed out after {DEFAULT_VERIFICATION_TIMEOUT}s",
            agent="VerificationCycle"
        )
        return False
    except Exception as e:
        logger.log_error(f"Verification cycle error: {e}", agent="VerificationCycle")
        return False


async def _execute_with_agent(
    task: AgentTask,
    task_type: str,
    logger,
    state_manager
) -> bool:
    """Execute task with appropriate agent directly.
    
    Args:
        task: Task to execute
        task_type: Type of task
        logger: Trace logger
        state_manager: State manager instance
        
    Returns:
        True if task succeeded, False otherwise
    """
    from aegis.core.llm_config import get_default_model
    
    # Get default model
    model = get_default_model()
    
    # Map task types to agent classes
    agent_map = {
        "code": CoderAgent,
        "test": TesterAgent,
        "review": CriticAgent,
        "documentation": JanitorAgent,
    }
    
    agent_class = agent_map.get(task_type, CoderAgent)
    agent = agent_class(model=model)
    
    logger.log_info(f"Executing with {agent.name} agent", agent=agent.name)
    
    try:
        # Execute with retry logic and timeout
        max_retries = task.max_retries
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.log_info(f"Retry attempt {attempt}/{max_retries}", agent=agent.name)
            
            try:
                # Execute with timeout
                response = await asyncio.wait_for(
                    agent.process(task),
                    timeout=DEFAULT_TASK_TIMEOUT
                )
                
                # Store reasoning
                await state_manager.store_reasoning(
                    task.id,
                    agent.name,
                    response.reasoning_trace
                )
                
                if response.status == "SUCCESS":
                    return True
                
                # Check if we should retry
                if attempt < max_retries and response.status in ["FAIL", "RETRY"]:
                    # Preserve retry history in context
                    if "retry_history" not in task.context:
                        task.context["retry_history"] = []
                    task.context["retry_history"].append({
                        "attempt": attempt,
                        "errors": response.errors,
                        "status": response.status
                    })
                    # Update current errors for next attempt
                    task.context["previous_errors"] = response.errors
                    continue
                
                # Max retries exhausted or non-retriable error
                logger.log_error(
                    f"Agent execution failed: {', '.join(response.errors)}",
                    agent=agent.name
                )
                return False
            
            except asyncio.TimeoutError:
                logger.log_error(
                    f"Agent execution timed out after {DEFAULT_TASK_TIMEOUT}s",
                    agent=agent.name
                )
                if attempt < max_retries:
                    continue
                return False
        
        return False
    
    except Exception as e:
        logger.log_error(f"Agent execution error: {e}", agent=agent.name)
        return False


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
        from aegis.core.llm_config import get_default_model
        model = get_default_model()
        orchestrator = OrchestratorAgent(model=model)
        
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
            
            # Execute subtasks
            execution_success = await _execute_subtasks(
                subtasks, 
                task_id, 
                logger, 
                state_manager,
                no_verify
            )
            
            # Update task status based on execution
            final_status = "SUCCESS" if execution_success else "FAILED"
            await state_manager.update_task_status(task_id, final_status, completed=True)
            await state_manager.store_reasoning(task_id, "orchestrator", response.reasoning_trace)
            
            if execution_success:
                logger.finalize(success=True)
                console.print("\n[green]✓ Task completed successfully![/green]\n")
            else:
                logger.finalize(success=False)
                console.print("\n[red]✗ Task execution failed[/red]\n")
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


@app.command()
def doctor() -> None:
    """Run health checks on the Aegis-CLI installation."""
    asyncio.run(_run_doctor())


async def _run_doctor() -> None:
    """Run health checks asynchronously."""
    console.print("\n[bold cyan]Aegis-CLI Health Check[/bold cyan]\n")
    
    checks = []
    
    # Check Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    python_ok = sys.version_info >= (3, 11)
    checks.append(("Python Version", f"{python_version}", python_ok))
    
    # Check dependencies
    try:
        import pydantic_ai
        checks.append(("PydanticAI", "Installed", True))
    except ImportError:
        checks.append(("PydanticAI", "Not installed", False))
    
    try:
        import anthropic
        checks.append(("Anthropic SDK", "Installed", True))
    except ImportError:
        checks.append(("Anthropic SDK", "Not installed", False))
    
    # Check for API keys
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    checks.append(("Anthropic API Key", "Configured" if anthropic_key else "Not configured", bool(anthropic_key)))
    
    google_key = os.getenv("GOOGLE_API_KEY")
    checks.append(("Google API Key", "Configured" if google_key else "Not configured", bool(google_key)))
    
    # Check database
    db_path = Path(".aegis/session.db")
    checks.append(("Database", "Exists" if db_path.exists() else "Not initialized", True))
    
    # Check logs directory
    logs_path = Path(".aegis/logs")
    checks.append(("Logs Directory", "Exists" if logs_path.exists() else "Not created", True))
    
    # Check tools
    registry = get_registry()
    tool_count = len(registry.list_available_tools())
    checks.append(("Available Tools", str(tool_count), tool_count > 0))
    
    # Display results
    table = Table()
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Result", style="white")
    
    all_critical_ok = True
    for name, status, ok in checks:
        status_icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, status_icon)
        
        # Critical checks
        if name in ["Python Version", "Available Tools"] and not ok:
            all_critical_ok = False
    
    console.print(table)
    
    if all_critical_ok:
        console.print("\n[bold green]✓ All critical checks passed![/bold green]\n")
    else:
        console.print("\n[bold red]✗ Some critical checks failed. Please review.[/bold red]\n")
    
    # Recommendations
    if not anthropic_key and not google_key:
        console.print("[yellow]Recommendation:[/yellow] Configure at least one LLM provider API key")
        console.print("  Set ANTHROPIC_API_KEY or GOOGLE_API_KEY in your .env file\n")


@app.command()
def validate() -> None:
    """Validate configuration and environment setup."""
    asyncio.run(_validate_config())


async def _validate_config() -> None:
    """Validate configuration asynchronously."""
    console.print("\n[bold cyan]Configuration Validation[/bold cyan]\n")
    
    issues = []
    warnings = []
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        warnings.append("No .env file found. Copy .env.example to .env and configure.")
    
    # Check LLM providers
    has_provider = False
    
    if os.getenv("ANTHROPIC_API_KEY"):
        has_provider = True
        console.print("[green]✓[/green] Anthropic API key configured")
    else:
        console.print("[yellow]○[/yellow] Anthropic API key not configured")
    
    if os.getenv("GOOGLE_API_KEY"):
        has_provider = True
        console.print("[green]✓[/green] Google API key configured")
    else:
        console.print("[yellow]○[/yellow] Google API key not configured")
    
    if os.getenv("OLLAMA_MODEL"):
        has_provider = True
        console.print("[green]✓[/green] Ollama model configured")
    else:
        console.print("[yellow]○[/yellow] Ollama model not configured")
    
    if not has_provider:
        issues.append("No LLM provider configured. Set at least one API key or model.")
    
    # Check directories
    aegis_dir = Path(".aegis")
    if not aegis_dir.exists():
        console.print("[yellow]○[/yellow] .aegis directory will be created on first run")
    else:
        console.print("[green]✓[/green] .aegis directory exists")
    
    # Check tool registry
    registry = get_registry()
    tool_count = len(registry.list_available_tools())
    console.print(f"[green]✓[/green] {tool_count} tools available")
    
    # Summary
    console.print()
    if issues:
        console.print("[bold red]Issues found:[/bold red]")
        for issue in issues:
            console.print(f"  [red]✗[/red] {issue}")
    
    if warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warning in warnings:
            console.print(f"  [yellow]![/yellow] {warning}")
    
    if not issues:
        console.print("[bold green]✓ Configuration is valid![/bold green]\n")
    else:
        console.print("\n[bold red]✗ Please fix the issues above before running tasks.[/bold red]\n")


@app.callback()
def callback() -> None:
    """Aegis-CLI: A modular, self-correcting multi-agent framework."""
    pass


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
