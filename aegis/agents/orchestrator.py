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
from aegis.core.llm_logger import LLMLogger


class OrchestratorAgent(BaseAgent):
    """Orchestrator for task decomposition and coordination.
    
    This agent analyzes user prompts and delegates work to specialized
    agents while managing dependencies and verification.
    """
    
    def __init__(
        self,
        mcp_config_path: str | Path | None = None,
        model: Model | None = None,
        verbose: bool = False
    ) -> None:
        """Initialize the orchestrator agent.
        
        Args:
            mcp_config_path: Optional path to MCP configuration file
            model: Optional PydanticAI Model to use
            verbose: Whether to enable verbose LLM logging
        """
        super().__init__("orchestrator", model=model)
        self.registry = get_registry()
        self.workspace_manager = WorkspaceManager()
        self.parser = LLMResponseParser(strict=False, log_failures=True)
        self.mcp_config_path = mcp_config_path
        self._mcp_servers: list[MCPServerConfig] = []
        self.llm_logger = LLMLogger(verbose=verbose)
        
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
    
    def _generate_workspace_name(self, description: str) -> str:
        """Generate a smart workspace name from task description.
        
        Args:
            description: Task description
            
        Returns:
            Sanitized workspace name
        
        Examples:
            "Create a Product model" → "product_model"
            "Build REST API for users" → "users_rest_api"
            "HTML calculator app" → "html_calculator_app"
            "Implement authentication system" → "authentication_system"
        """
        # Convert to lowercase
        name = description.lower()
        
        # Remove common filler words
        filler_words = [
            'create', 'build', 'make', 'generate', 'implement', 'develop',
            'add', 'write', 'a', 'an', 'the', 'for', 'with', 'using',
            'me', 'please', 'can', 'you', 'could', 'would', 'should'
        ]
        
        words = name.split()
        meaningful_words = [w for w in words if w not in filler_words]
        
        # If we removed too much, keep first 3-4 words
        if len(meaningful_words) < 2:
            meaningful_words = words[:4]
        
        # Join with underscores
        name = '_'.join(meaningful_words)
        
        # Remove special characters, keep only alphanumeric and underscores
        name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)
        
        # Remove consecutive underscores
        while '__' in name:
            name = name.replace('__', '_')
        
        # Trim underscores from start/end
        name = name.strip('_')
        
        # Limit length
        if len(name) > 50:
            name = name[:50].rsplit('_', 1)[0]  # Cut at word boundary
        
        # Fallback if empty
        if not name:
            from datetime import datetime
            name = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return name
    
    async def _create_execution_plan(
        self,
        task: AgentTask,
        context: dict
    ) -> dict:
        """Create execution plan using LLM WITHOUT tools (text-based planning).
        
        Tools don't work reliably with Llama 3.1, so we use prompt engineering
        with embedded context instead of tool calls.
        
        Args:
            task: Task to plan for
            context: Context gathered from tools
            
        Returns:
            Execution plan with files to create/modify
        """
        task_description = task.payload.get('description', '')
        
        # Get current workspace info (direct access, not via LLM tools)
        workspace_name = self._generate_workspace_name(task_description)
        
        # Build enhanced planning prompt with embedded "tool" information
        planning_prompt = f"""Analyze this request and create a file execution plan.

USER REQUEST: {task_description}

WORKSPACE INFORMATION:
- Suggested workspace name: {workspace_name}
- Current workspace: {context.get('workspace', {}).get('name', 'None')}
- Existing files: {len(context.get('workspace', {}).get('files', []))}
- Has models: {context.get('has_models', False)}
- Has tests: {context.get('has_tests', False)}

INSTRUCTIONS:
1. Determine what files need to be created
2. For web apps (HTML/JS/CSS), create proper structure:
   - HTML files in src/ or root
   - JavaScript in src/js/ or src/
   - CSS in src/css/ or src/
   - Tests if applicable (can be HTML or pytest)

3. For Python projects, create:
   - Source files in src/
   - Tests in tests/
   - Follow existing patterns if workspace exists

4. Choose descriptive workspace name:
   - Use snake_case
   - Be specific: "html_calculator_app" not "project"
   - Max 50 characters

RESPOND WITH VALID JSON (no markdown, no explanation):
{{
    "workspace_name": "descriptive_name",
    "use_existing_workspace": false,
    "files_to_create": [
        {{"path": "src/calculator.html", "purpose": "Main HTML calculator interface"}},
        {{"path": "src/calculator.js", "purpose": "Calculator logic"}},
        {{"path": "src/styles.css", "purpose": "Styling"}}
    ],
    "files_to_modify": [],
    "creation_order": ["src/calculator.html", "src/calculator.js", "src/styles.css"],
    "reasoning": "Brief explanation of structure"
}}

IMPORTANT: Return ONLY the JSON, no other text."""

        # Create planning agent WITHOUT tools (text-based)
        planning_agent = PydanticAgent(
            model=self.get_model(),
            # NO TOOLS - just text generation
            system_prompt="You are a planning agent that creates file execution plans. Return only valid JSON."
        )
        
        # LOG PROMPT
        interaction_id = self.llm_logger.log_prompt(
            agent_name="OrchestratorAgent (Planning)",
            prompt=planning_prompt,
            model=str(self.get_model()),
            system_prompt="You are a planning agent that creates file execution plans. Return only valid JSON.",
            tools=None  # No tools - text-based planning
        )
        
        # Get plan
        result = await planning_agent.run(planning_prompt)
        plan_text = self.parser.parse(result, content_type='text')
        
        # LOG RESPONSE
        self.llm_logger.log_response(
            interaction_id=interaction_id,
            agent_name="OrchestratorAgent (Planning)",
            response=result,
            extracted_content=plan_text,
            finish_reason="stop"
        )
        
        # Parse JSON from response
        try:
            # Try direct JSON parse
            plan = json.loads(plan_text)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown or text
            # Use a more sophisticated approach to find JSON boundaries
            # Look for the first complete JSON object
            json_match = re.search(r'\{[\s\S]*?\}', plan_text)
            if json_match:
                try:
                    plan = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    # If non-greedy didn't work, try finding a properly nested JSON
                    # This handles cases where JSON might have nested objects
                    depth = 0
                    start_idx = plan_text.find('{')
                    if start_idx != -1:
                        for i, char in enumerate(plan_text[start_idx:], start=start_idx):
                            if char == '{':
                                depth += 1
                            elif char == '}':
                                depth -= 1
                                if depth == 0:
                                    try:
                                        plan = json.loads(plan_text[start_idx:i+1])
                                        break
                                    except json.JSONDecodeError:
                                        pass
                        else:
                            # Fallback: create basic plan
                            plan = self._create_fallback_plan(task)
                    else:
                        # Fallback: create basic plan
                        plan = self._create_fallback_plan(task)
            else:
                # Fallback: create basic plan
                plan = self._create_fallback_plan(task)
        
        # Ensure workspace name is smart, not generic
        if plan.get('workspace_name') in ['project', 'default', 'workspace', 'descriptive_name', 'feature_name', None, '']:
            plan['workspace_name'] = workspace_name
        
        return plan
    
    def _create_fallback_plan(self, task: AgentTask) -> dict:
        """Create a fallback plan when LLM planning fails.
        
        Args:
            task: Task to create plan for
            
        Returns:
            Basic execution plan
        """
        # Reuse WorkspaceManager's sanitization logic for consistency
        raw_name = task.payload.get("description", "project")[:50]
        workspace_name = WorkspaceManager.sanitize_name(raw_name)
        
        return {
            "workspace_name": workspace_name,
            "use_existing_workspace": False,
            "files_to_create": [
                {"path": "src/main.py", "purpose": task.payload.get("description")}
            ],
            "files_to_modify": [],
            "creation_order": ["src/main.py"],
            "reasoning": "Basic single-file plan"
        }
    
    def _find_related_files(self, file_path: str, plan: dict) -> dict:
        """Find files related to the given file based on the plan.
        
        This helps CoderAgent understand what files it should reference.
        For example, if generating an HTML file, this returns JS and CSS files.
        
        Args:
            file_path: Path of the file being generated
            plan: Execution plan with all files to create
            
        Returns:
            Dictionary with related files categorized by type
        """
        from pathlib import Path
        
        related = {
            "javascript": [],
            "stylesheets": [],
            "html": [],
            "other": []
        }
        
        # Get file extension to determine what we're generating
        current_ext = Path(file_path).suffix.lower()
        
        # Get all files from plan
        all_files = plan.get("files_to_create", [])
        
        for file_spec in all_files:
            other_path = file_spec["path"]
            
            # Skip self
            if other_path == file_path:
                continue
            
            other_ext = Path(other_path).suffix.lower()
            
            # Categorize related files
            if other_ext in ['.js', '.mjs']:
                related["javascript"].append(other_path)
            elif other_ext in ['.css']:
                related["stylesheets"].append(other_path)
            elif other_ext in ['.html', '.htm']:
                related["html"].append(other_path)
            else:
                related["other"].append(other_path)
        
        # If we're generating HTML, prioritize JS and CSS files
        # If we're generating JS/CSS, note what HTML files might import them
        return related
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a task with smart planning and workspace management.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with results
        """
        try:
            # Validate input early
            description = task.payload.get('description', '').strip()
            if not description:
                return AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="Task description is empty or missing",
                    errors=["No task description provided. Please specify what you want to create."]
                )
            
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
            coder = CoderAgent(model=self.get_model(), verbose=self.llm_logger.verbose)
            
            generated_files = []
            
            # Get original user request for context
            original_description = task.payload.get("description", "")
            
            for file_spec in plan.get("files_to_create", []):
                file_path = file_spec["path"]
                file_purpose = file_spec["purpose"]
                
                # Compute full workspace path for file writing
                full_file_path = self.workspace_manager.get_workspace_path(file_path)
                
                # Build rich description combining original request and file purpose
                # Only append original description if it's not already the same as file_purpose
                # to avoid redundant descriptions like "Product model for Create a Product model"
                if original_description and file_purpose != original_description:
                    full_description = f"{file_purpose} for {original_description}"
                else:
                    full_description = file_purpose
                
                # Find related files for this file
                related_files = self._find_related_files(file_path, plan)
                
                # Create task for CoderAgent with rich context including file relationships
                code_task = AgentTask(
                    id=f"{task.id}_code_{len(generated_files)}",
                    type="code",
                    payload={
                        "description": full_description,
                        "file_path": str(full_file_path),
                        "context": {
                            "workspace": workspace_name,
                            "existing_files": context["workspace"].get("files", []),
                            "plan": plan.get("reasoning", ""),
                            "original_request": original_description,
                            "all_files": plan.get("files_to_create", []),
                            "related_files": related_files
                        }
                    },
                    context=task.context
                )
                
                # Generate code (CoderAgent has no tools - just generates text)
                code_response = await coder.process(code_task)
                
                if code_response.status != "SUCCESS":
                    continue
                
                # Extract generated code from response
                generated_code = code_response.data.get("code", "")
                
                # CoderAgent now handles writing files directly with full path
                # Just track successful code generation
                if generated_code:
                    generated_files.append({
                        "path": file_path,
                        "full_path": str(full_file_path),
                        "purpose": file_purpose
                    })
            
            # Check if files were created successfully
            expected_files = len(plan.get("files_to_create", []))
            
            if len(generated_files) == 0:
                return AgentResponse(
                    status="FAIL",
                    data={
                        "workspace": workspace_name,
                        "workspace_path": str(workspace),
                        "files_created": [],
                        "plan": plan
                    },
                    reasoning_trace=f"Failed to create any files. Expected {expected_files} files.",
                    errors=[f"No files were created out of {expected_files} planned"]
                )
            
            # Check if all files were created
            if len(generated_files) < expected_files:
                # Partial file creation is treated as failure - some files missing
                return AgentResponse(
                    status="FAIL",
                    data={
                        "workspace": workspace_name,
                        "workspace_path": str(workspace),
                        "files_created": generated_files,
                        "plan": plan
                    },
                    reasoning_trace=f"Created {len(generated_files)}/{expected_files} files in workspace '{workspace_name}'",
                    errors=[f"Only {len(generated_files)}/{expected_files} files created"]
                )
            
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
