"""Git tool for Aegis-CLI.

Provides Git operations like status, diff, log, and branch management.
"""

import asyncio
import subprocess
from typing import Any

from aegis.tools.base_tool import Tool, ToolResult


class GitTool(Tool):
    """Tool for Git operations.
    
    Provides capabilities for common Git operations including
    status, diff, log, branch management, and more.
    """
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "git"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "Git operations: status, diff, log, branch, and commit info"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "status", "diff", "log", "branch", "show",
                        "list_branches", "current_branch", "add", "commit"
                    ],
                    "description": "Git action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "Path or file to operate on"
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (for branch operations)"
                },
                "commit": {
                    "type": "string",
                    "description": "Commit hash (for show operation)"
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (for commit operation)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Limit number of results (for log)",
                    "default": 10
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show only staged changes (for diff)",
                    "default": False
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the Git operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult containing operation results
        """
        action = kwargs.get("action")
        
        try:
            if action == "status":
                return await self._status()
            elif action == "diff":
                return await self._diff(
                    kwargs.get("path"),
                    kwargs.get("staged", False)
                )
            elif action == "log":
                return await self._log(kwargs.get("limit", 10))
            elif action == "branch":
                return await self._branch(kwargs.get("branch"))
            elif action == "show":
                return await self._show(kwargs.get("commit", "HEAD"))
            elif action == "list_branches":
                return await self._list_branches()
            elif action == "current_branch":
                return await self._current_branch()
            elif action == "add":
                return await self._add(kwargs.get("path", "."))
            elif action == "commit":
                return await self._commit(kwargs.get("message", ""))
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _run_git_command(self, args: list[str]) -> tuple[bool, str, str]:
        """Run a git command and return output.
        
        Args:
            args: Git command arguments
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "git", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            
            return (
                success,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace")
            )
        except Exception as e:
            return False, "", str(e)
    
    async def _status(self) -> ToolResult:
        """Get git status.
        
        Returns:
            ToolResult with status information
        """
        success, stdout, stderr = await self._run_git_command(["status", "--short"])
        
        if not success:
            return ToolResult(success=False, error=stderr or "Failed to get status")
        
        return ToolResult(
            success=True,
            data={"status": stdout, "summary": self._parse_status(stdout)}
        )
    
    def _parse_status(self, status_output: str) -> dict[str, Any]:
        """Parse git status output.
        
        Args:
            status_output: Output from git status --short
            
        Returns:
            Dictionary with parsed status
        """
        lines = status_output.strip().split("\n")
        modified = []
        added = []
        deleted = []
        untracked = []
        
        for line in lines:
            if not line:
                continue
            
            status = line[:2]
            filename = line[3:]
            
            if status.startswith("M"):
                modified.append(filename)
            elif status.startswith("A"):
                added.append(filename)
            elif status.startswith("D"):
                deleted.append(filename)
            elif status.startswith("??"):
                untracked.append(filename)
        
        return {
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "untracked": untracked,
            "total_changes": len(modified) + len(added) + len(deleted)
        }
    
    async def _diff(self, path: str | None, staged: bool) -> ToolResult:
        """Get git diff.
        
        Args:
            path: Optional file path
            staged: Show staged changes
            
        Returns:
            ToolResult with diff
        """
        args = ["diff"]
        if staged:
            args.append("--cached")
        if path:
            args.append(path)
        
        success, stdout, stderr = await self._run_git_command(args)
        
        if not success:
            return ToolResult(success=False, error=stderr or "Failed to get diff")
        
        return ToolResult(success=True, data={"diff": stdout})
    
    async def _log(self, limit: int) -> ToolResult:
        """Get git log.
        
        Args:
            limit: Number of commits to show
            
        Returns:
            ToolResult with log entries
        """
        args = [
            "log",
            f"-{limit}",
            "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=iso"
        ]
        
        success, stdout, stderr = await self._run_git_command(args)
        
        if not success:
            return ToolResult(success=False, error=stderr or "Failed to get log")
        
        commits = []
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            
            parts = line.split("|")
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4]
                })
        
        return ToolResult(success=True, data={"commits": commits})
    
    async def _branch(self, branch_name: str | None) -> ToolResult:
        """List or create branches.
        
        Args:
            branch_name: Branch name to create
            
        Returns:
            ToolResult with branch info
        """
        if branch_name:
            # Create new branch
            success, stdout, stderr = await self._run_git_command(
                ["branch", branch_name]
            )
            if not success:
                return ToolResult(
                    success=False,
                    error=stderr or f"Failed to create branch: {branch_name}"
                )
            return ToolResult(
                success=True,
                data={"message": f"Branch created: {branch_name}"}
            )
        else:
            # List branches
            return await self._list_branches()
    
    async def _show(self, commit: str) -> ToolResult:
        """Show commit details.
        
        Args:
            commit: Commit hash or reference
            
        Returns:
            ToolResult with commit details
        """
        success, stdout, stderr = await self._run_git_command(["show", commit])
        
        if not success:
            return ToolResult(
                success=False,
                error=stderr or f"Failed to show commit: {commit}"
            )
        
        return ToolResult(success=True, data={"commit": stdout})
    
    async def _list_branches(self) -> ToolResult:
        """List all branches.
        
        Returns:
            ToolResult with branch list
        """
        success, stdout, stderr = await self._run_git_command(["branch", "-a"])
        
        if not success:
            return ToolResult(success=False, error=stderr or "Failed to list branches")
        
        branches = []
        current = None
        
        for line in stdout.strip().split("\n"):
            if not line:
                continue
            
            is_current = line.startswith("*")
            branch_name = line[2:].strip()
            
            branches.append(branch_name)
            if is_current:
                current = branch_name
        
        return ToolResult(
            success=True,
            data={"branches": branches, "current": current}
        )
    
    async def _current_branch(self) -> ToolResult:
        """Get current branch name.
        
        Returns:
            ToolResult with current branch
        """
        success, stdout, stderr = await self._run_git_command(
            ["branch", "--show-current"]
        )
        
        if not success:
            return ToolResult(
                success=False,
                error=stderr or "Failed to get current branch"
            )
        
        return ToolResult(
            success=True,
            data={"branch": stdout.strip()}
        )
    
    async def _add(self, path: str) -> ToolResult:
        """Add files to staging area.
        
        Args:
            path: File or directory path
            
        Returns:
            ToolResult with success status
        """
        success, stdout, stderr = await self._run_git_command(["add", path])
        
        if not success:
            return ToolResult(
                success=False,
                error=stderr or f"Failed to add: {path}"
            )
        
        return ToolResult(
            success=True,
            data={"message": f"Added to staging: {path}"}
        )
    
    async def _commit(self, message: str) -> ToolResult:
        """Create a commit.
        
        Args:
            message: Commit message
            
        Returns:
            ToolResult with commit info
        """
        if not message:
            return ToolResult(success=False, error="Commit message is required")
        
        success, stdout, stderr = await self._run_git_command(["commit", "-m", message])
        
        if not success:
            return ToolResult(
                success=False,
                error=stderr or "Failed to commit"
            )
        
        return ToolResult(
            success=True,
            data={"message": "Commit created", "output": stdout}
        )
