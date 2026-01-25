"""Verification cycle engine for self-correction.

Implements the Plan-Execute-Verify lifecycle with retry logic.
"""

from typing import Any
from rich.console import Console
from rich.prompt import Confirm

from aegis.agents.base import AgentTask, AgentResponse, BaseAgent
from aegis.core.logging import TraceLogger


class VerificationCycle:
    """Self-correction engine using Plan-Execute-Verify lifecycle.
    
    Coordinates between coder, tester, and critic agents to ensure
    code quality through iterative refinement.
    """
    
    def __init__(
        self,
        coder: BaseAgent,
        tester: BaseAgent,
        critic: BaseAgent,
        logger: TraceLogger
    ) -> None:
        """Initialize verification cycle.
        
        Args:
            coder: Coder agent for generating code
            tester: Tester agent for validation
            critic: Critic agent for review
            logger: Trace logger
        """
        self.coder = coder
        self.tester = tester
        self.critic = critic
        self.logger = logger
        self.console = Console()
    
    async def run(self, task: AgentTask) -> AgentResponse:
        """Run the verification cycle.
        
        The cycle:
        1. Coder generates/modifies code
        2. Tester validates (with retries)
        3. Critic reviews (pass/fail)
        4. Loop until SUCCESS or max_retries
        
        Args:
            task: Task to process
            
        Returns:
            Final AgentResponse
        """
        max_retries = task.max_retries
        attempt = 0
        
        self.logger.log_info(
            f"Starting verification cycle (max retries: {max_retries})",
            agent="VerificationCycle"
        )
        
        while attempt <= max_retries:
            attempt += 1
            self.logger.log_info(
                f"Attempt {attempt}/{max_retries + 1}",
                agent="VerificationCycle"
            )
            
            # Step 1: Coder generates code
            self.logger.log_agent_thought(
                "Coder",
                f"Generating code for task: {task.type}"
            )
            
            coder_response = await self.coder.process(task)
            
            if coder_response.status == "FAIL":
                self.logger.log_error(
                    f"Coder failed: {', '.join(coder_response.errors)}",
                    agent="Coder"
                )
                if attempt > max_retries:
                    return coder_response
                continue
            
            # Step 2: Tester validates
            self.logger.log_agent_thought(
                "Tester",
                "Validating generated code"
            )
            
            test_task = AgentTask(
                id=f"{task.id}_test_{attempt}",
                type="test",
                payload=coder_response.data,
                context=task.context
            )
            
            tester_response = await self.tester.process(test_task)
            
            if tester_response.status == "FAIL":
                self.logger.log_error(
                    f"Tests failed: {', '.join(tester_response.errors)}",
                    agent="Tester"
                )
                
                if attempt > max_retries:
                    return tester_response
                
                # Update task context with test feedback
                task.context["previous_attempt"] = coder_response.data
                task.context["test_feedback"] = tester_response.errors
                continue
            
            # Step 3: Critic reviews
            self.logger.log_agent_thought(
                "Critic",
                "Reviewing code quality and security"
            )
            
            review_task = AgentTask(
                id=f"{task.id}_review_{attempt}",
                type="review",
                payload=coder_response.data,
                context=task.context
            )
            
            critic_response = await self.critic.process(review_task)
            
            if critic_response.status == "SUCCESS":
                self.logger.log_result(
                    "Code passed all checks!",
                    agent="VerificationCycle"
                )
                return AgentResponse(
                    status="SUCCESS",
                    data=coder_response.data,
                    reasoning_trace=f"Verification completed in {attempt} attempts",
                    tool_calls=(
                        coder_response.tool_calls +
                        tester_response.tool_calls +
                        critic_response.tool_calls
                    )
                )
            
            # Critic found issues
            self.logger.log_error(
                f"Review failed: {', '.join(critic_response.errors)}",
                agent="Critic"
            )
            
            if attempt > max_retries:
                # Ask for human intervention
                should_escalate = await self._should_escalate(task, critic_response)
                if should_escalate:
                    self.escalate_to_human(task, "Max retries exceeded")
                return critic_response
            
            # Update context for next iteration
            task.context["previous_attempt"] = coder_response.data
            task.context["review_feedback"] = critic_response.errors
        
        # Should not reach here, but handle gracefully
        return AgentResponse(
            status="FAIL",
            data={},
            reasoning_trace="Verification cycle exhausted all retries",
            errors=["Maximum retry attempts exceeded"]
        )
    
    async def _should_escalate(
        self,
        task: AgentTask,
        response: AgentResponse
    ) -> bool:
        """Determine if issue should escalate to human.
        
        Args:
            task: Current task
            response: Failed response
            
        Returns:
            True if should escalate
        """
        # For now, always return True for human review
        # Can be made more sophisticated based on error types
        return True
    
    def escalate_to_human(self, task: AgentTask, reason: str) -> None:
        """Escalate to human intervention.
        
        Args:
            task: Task that needs intervention
            reason: Reason for escalation
        """
        self.logger.log_error(
            f"Escalating to human: {reason}",
            agent="VerificationCycle"
        )
        
        self.console.print("\n[bold red]Human Intervention Required[/bold red]")
        self.console.print(f"Task ID: {task.id}")
        self.console.print(f"Reason: {reason}")
        self.console.print("\nPlease review the task and provide guidance.\n")
        
        # Optionally wait for user input
        if Confirm.ask("Continue with manual review?"):
            self.console.print("[yellow]Please manually review and fix the issues.[/yellow]")
