"""Orchestrator agent for task decomposition and delegation.

The orchestrator is responsible for:
- Parsing user prompts into structured tasks
- Building task dependency graphs
- Delegating to specialized agents
- Coordinating the verification cycle
"""

import uuid
import json
import re
from pathlib import Path
from typing import Any
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse, MCPServerConfig
from aegis.core.mcp_client import load_mcp_config, filter_servers_by_name
from aegis.core.workspace import WorkspaceManager
from aegis.core.llm_response_parser import LLMResponseParser
from aegis.tools.registry import get_registry


class OrchestratorAgent(BaseAgent):
    """Orchestrator for task decomposition and coordination.
    
    This agent analyzes user prompts and delegates work to specialized
    agents while managing dependencies and verification.
    """
    
    def __init__(
        self,
        mcp_config_path: str | Path | None = None,
        model: Model | None = None
    ) -> None:
        """Initialize the orchestrator agent.
        
        Args:
            mcp_config_path: Optional path to MCP configuration file
            model: Optional PydanticAI Model to use
        """
        super().__init__("orchestrator", model=model)
        self.registry = get_registry()
        self.workspace_manager = WorkspaceManager()
        self.parser = LLMResponseParser(strict=False, log_failures=True)
        self.mcp_config_path = mcp_config_path
        self._mcp_servers: list[MCPServerConfig] = []
        
        # Load MCP config if available
        if mcp_config_path:
            try:
                self._mcp_servers = load_mcp_config(mcp_config_path)
            except (FileNotFoundError, ValueError):
                # Config file not found or invalid, continue without MCP
                pass
    
    def get_mcp_servers_for_agent(
        self, 
        agent_name: str,
        server_names: list[str] | None = None
    ) -> list[MCPServerConfig]:
        """Get MCP servers to equip a specific agent with.
        
        Args:
            agent_name: Name of the agent
            server_names: Optional list of server names to filter by
            
        Returns:
            List of MCP server configurations for the agent
        """
        if not self._mcp_servers:
            return []
        
        if server_names:
            return filter_servers_by_name(self._mcp_servers, server_names)
        
        # Return all servers by default
        return self._mcp_servers.copy()
    
    async def _gather_context(self, task: AgentTask) -> dict:
        """Gather context using tools before code generation.
        
        Args:
            task: Current task
            
        Returns:
            Context dictionary with workspace info, existing files, etc.
        """
        context = {}
        
        # Get workspace info if one is active
        workspace_info = self.workspace_manager.workspace_info()
        context["workspace"] = workspace_info
        
        # Get project structure using context tool
        context_tool = self.registry.get_tool("context")
        if context_tool:
            structure_result = await context_tool.execute(action="get_structure")
            if structure_result.success:
                context["project_structure"] = structure_result.data
        
        # List files in workspace if it exists
        if workspace_info.get("path"):
            fs_tool = self.registry.get_tool("filesystem")
            if fs_tool:
                files_result = await fs_tool.execute(
                    action="list_directory",
                    path=workspace_info["path"]
                )
                if files_result.success:
                    context["workspace_files"] = files_result.data
        
        # Check for existing patterns (e.g., models/, views/, etc.)
        context["has_models"] = any("models" in f for f in workspace_info.get("files", []))
        context["has_tests"] = any("test" in f for f in workspace_info.get("files", []))
        
        return context
    
    async def _create_execution_plan(
        self,
        task: AgentTask,
        context: dict
    ) -> dict:
        """Create execution plan using LLM with tools.
        
        Args:
            task: Task to plan for
            context: Context gathered from tools
            
        Returns:
            Execution plan with files to create/modify
        """
        from aegis.core.tool_bridge import create_toolset_from_registry
        
        # Create planning prompt
        planning_prompt = f"""Analyze this request and create a file execution plan:

REQUEST: {task.payload.get('description', '')}

WORKSPACE CONTEXT:
- Current workspace: {context['workspace'].get('name', 'None')}
- Existing files: {len(context['workspace'].get('files', []))}
- Has models: {context.get('has_models', False)}
- Has tests: {context.get('has_tests', False)}

TASK:
1. Use filesystem tools to check what exists
2. Use context tools to understand existing patterns
3. Return a JSON plan with:
   - workspace_name: Name for workspace (new or existing)
   - files_to_create: List of files with paths and purposes
   - files_to_modify: List of existing files to update
   - dependencies: Order of file creation

RESPOND WITH JSON:
{{
    "workspace_name": "feature_name",
    "use_existing_workspace": false,
    "files_to_create": [
        {{"path": "src/models/product.py", "purpose": "Product model class"}},
        {{"path": "tests/test_product.py", "purpose": "Product tests"}}
    ],
    "files_to_modify": [],
    "creation_order": ["src/models/product.py", "tests/test_product.py"],
    "reasoning": "Create Product model following existing patterns..."
}}
"""
        
        # Create planning agent WITH tools
        toolset = create_toolset_from_registry(self.registry)
        planning_agent = PydanticAgent(
            model=self.get_model(),
            tools=toolset,
            system_prompt="""You are a planning agent.
        
Your job: Analyze requests and create file execution plans.

Use tools to:
- Check existing files (filesystem)
- Understand project structure (context)
- List directory contents (filesystem)

Return a detailed JSON plan."""
        )
        
        result = await planning_agent.run(planning_prompt)
        
        # Parse the plan from response
        plan_text = self.parser.parse(result, content_type='text')
        
        # Extract JSON from response (might be wrapped in markdown)
        # Try to find JSON in response
        json_match = re.search(r'\{.*\}', plan_text, re.DOTALL)
        if json_match:
            try:
                plan = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Fallback: create basic plan
                plan = self._create_fallback_plan(task)
        else:
            # Fallback: create basic plan
            plan = self._create_fallback_plan(task)
        
        return plan
    
    def _create_fallback_plan(self, task: AgentTask) -> dict:
        """Create a fallback plan when LLM planning fails.
        
        Args:
            task: Task to create plan for
            
        Returns:
            Basic execution plan
        """
        return {
            "workspace_name": task.payload.get("description", "project").lower().replace(" ", "_")[:50],
            "use_existing_workspace": False,
            "files_to_create": [
                {"path": "src/main.py", "purpose": task.payload.get("description")}
            ],
            "files_to_modify": [],
            "creation_order": ["src/main.py"],
            "reasoning": "Basic single-file plan"
        }
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a task with smart planning and workspace management.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with results
        """
        try:
            # PHASE 1: PLANNING (with tools)
            context = await self._gather_context(task)
            plan = await self._create_execution_plan(task, context)
            
            # PHASE 2: WORKSPACE SETUP
            workspace_name = plan.get("workspace_name", "default")
            use_existing = plan.get("use_existing_workspace", False)
            
            if use_existing:
                workspace = self.workspace_manager.use_workspace(workspace_name)
                if not workspace:
                    # Workspace doesn't exist, create it
                    workspace = self.workspace_manager.create_workspace(workspace_name)
            else:
                workspace = self.workspace_manager.create_workspace(workspace_name)
            
            # PHASE 3: CODE GENERATION (delegate to CoderAgent with context)
            from aegis.agents.coder import CoderAgent
            coder = CoderAgent(model=self.get_model())
            
            generated_files = []
            
            for file_spec in plan.get("files_to_create", []):
                file_path = file_spec["path"]
                file_purpose = file_spec["purpose"]
                
                # Create task for CoderAgent with rich context
                code_task = AgentTask(
                    id=f"{task.id}_code_{len(generated_files)}",
                    type="code",
                    payload={
                        "description": file_purpose,
                        "file_path": file_path,
                        "context": {
                            "workspace": workspace_name,
                            "existing_files": context["workspace"].get("files", []),
                            "plan": plan.get("reasoning", "")
                        }
                    },
                    context=task.context
                )
                
                # Generate code (CoderAgent has no tools - just generates text)
                code_response = await coder.process(code_task)
                
                if code_response.status != "SUCCESS":
                    continue
                
                generated_code = code_response.data.get("code", "")
                
                # PHASE 4: EXECUTION (write to workspace)
                fs_tool = self.registry.get_tool("filesystem")
                if fs_tool:
                    full_path = self.workspace_manager.get_workspace_path(file_path)
                    
                    # Ensure parent directory exists
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    write_result = await fs_tool.execute(
                        action="write_file",
                        path=str(full_path),
                        content=generated_code
                    )
                    
                    if write_result.success:
                        generated_files.append({
                            "path": file_path,
                            "full_path": str(full_path),
                            "purpose": file_purpose
                        })
            
            # Return success with workspace info
            return AgentResponse(
                status="SUCCESS",
                data={
                    "workspace": workspace_name,
                    "workspace_path": str(workspace),
                    "files_created": generated_files,
                    "plan": plan
                },
                reasoning_trace=f"Created {len(generated_files)} files in workspace '{workspace_name}'"
            )
            
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Orchestration failed: {e}",
                errors=[str(e)]
            )
    
    async def decompose_prompt(self, prompt: str) -> list[dict[str, Any]]:
        """Decompose a user prompt into structured tasks using LLM.
        
        Args:
            prompt: User prompt
            
        Returns:
            List of task dictionaries
        """
        from pydantic import BaseModel, Field
        
        # Define output structure for LLM
        class TaskDecomposition(BaseModel):
            """Structured task decomposition from user prompt."""
            tasks: list[dict[str, Any]] = Field(
                description="List of tasks with type, description, and priority"
            )
            reasoning: str = Field(
                description="Explanation of task breakdown"
            )
        
        try:
            # Get model
            model = self.get_model()
            
            # Create PydanticAI agent for task decomposition
            pydantic_agent = PydanticAgent(
                model=model,
                result_type=TaskDecomposition,
                system_prompt=self.get_system_prompt()
            )
            
            # Build prompt for task decomposition
            decomposition_prompt = f"""Analyze this user request and break it down into actionable tasks:

"{prompt}"

Create a structured task breakdown with:
- Task type (one of: "code", "test", "review", "documentation")
- Detailed description of what needs to be done
- Priority (1 = highest)

Each task should be atomic and actionable. Consider:
- What code needs to be written?
- What tests are needed?
- What documentation should be updated?
- Are there review/quality requirements?

Return the tasks in order of execution priority."""
            
            # Run LLM decomposition
            result = await pydantic_agent.run(decomposition_prompt)
            
            # Extract tasks from LLM response
            tasks = result.data.tasks
            
            # Validate and normalize task structure
            normalized_tasks = []
            for task in tasks:
                normalized_task = {
                    "type": task.get("type", "code"),
                    "description": task.get("description", prompt),
                    "priority": task.get("priority", 1)
                }
                normalized_tasks.append(normalized_task)
            
            # If no tasks generated, fall back to default
            if not normalized_tasks:
                normalized_tasks.append({
                    "type": "code",
                    "description": prompt,
                    "priority": 1
                })
            
            return normalized_tasks
            
        except Exception as e:
            # Fallback to simple keyword-based decomposition if LLM fails
            tasks = []
            
            # Check for code-related keywords
            code_keywords = ["create", "implement", "generate", "write", "code", "function"]
            if any(keyword in prompt.lower() for keyword in code_keywords):
                tasks.append({
                    "type": "code",
                    "description": f"Generate code: {prompt}",
                    "priority": 1
                })
            
            # Default to code task if nothing matches
            if not tasks:
                tasks.append({
                    "type": "code",
                    "description": prompt,
                    "priority": 1
                })
            
            return tasks
    
    async def execute_dag(
        self,
        tasks: list[AgentTask]
    ) -> dict[str, AgentResponse]:
        """Execute tasks respecting dependencies.
        
        Args:
            tasks: List of tasks to execute
            
        Returns:
            Dictionary mapping task IDs to responses
        """
        # Simple sequential execution for now
        # In production, would do topological sort and parallel execution
        
        results: dict[str, AgentResponse] = {}
        
        for task in tasks:
            # Check dependencies
            dependencies_met = all(
                dep in results and results[dep].status == "SUCCESS"
                for dep in task.dependencies
            )
            
            if not dependencies_met:
                results[task.id] = AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="Dependencies not met",
                    errors=["Required dependencies failed or incomplete"]
                )
                continue
            
            # Would delegate to appropriate agent here
            # For now, just mark as pending
            results[task.id] = AgentResponse(
                status="PENDING",
                data={},
                reasoning_trace="Task queued for execution"
            )
        
        return results
    
    def should_retry(self, response: AgentResponse, attempt: int) -> bool:
        """Determine if a failed task should be retried.
        
        Args:
            response: Agent response
            attempt: Current attempt number
            
        Returns:
            True if should retry
        """
        if response.status == "SUCCESS":
            return False
        
        # Retry FAIL and RETRY statuses
        if response.status in ["FAIL", "RETRY"]:
            # Check for non-retriable errors
            non_retriable = ["invalid_input", "missing_dependency"]
            for error in response.errors:
                if any(nr in error.lower() for nr in non_retriable):
                    return False
            
            return True
        
        return False
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input.
        
        Args:
            task: Task to validate
            
        Returns:
            True if valid
        """
        # Check required fields
        if "prompt" not in task.payload:
            return False
        
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt for orchestrator.
        
        Returns:
            System prompt
        """
        return """You are the Orchestrator Agent for Aegis-CLI.

Your role: Coordinate complex tasks using a three-phase approach:

PHASE 1: PLANNING (You have tools here!)
- Use filesystem tools to check existing files
- Use context tools to understand project structure
- Analyze what needs to be created/modified
- Create a detailed execution plan

PHASE 2: DELEGATION
- Break down tasks into subtasks
- Delegate to specialist agents:
  * CoderAgent: Code generation
  * TesterAgent: Test generation
  * CriticAgent: Code review
  * JanitorAgent: Cleanup tasks

PHASE 3: EXECUTION
- Create/use workspace for organized file management
- Write generated code to workspace
- Coordinate file operations
- Run tests and verification

WORKSPACE MANAGEMENT:
- Create new workspace: workspaces/<feature_name>/
- Or use existing workspace
- Organize files in logical structure:
  * src/ - Source code
  * tests/ - Test files
  * docs/ - Documentation

TOOLS AVAILABLE TO YOU:
- filesystem: Check/create files, list directories
- context: Get project structure
- shell: Run commands (carefully!)
- git: Version control operations

REMEMBER:
- Gather context BEFORE generating code
- Provide rich context to specialist agents
- Organize output in workspaces
- Track dependencies between files
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["context"]
