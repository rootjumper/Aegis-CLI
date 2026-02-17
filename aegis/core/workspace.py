"""Workspace management for organized code generation.

This module provides workspace management capabilities for the Aegis-CLI
orchestrator, enabling organized file creation and multi-file feature development.
"""

from pathlib import Path
from typing import Optional
from datetime import datetime


class WorkspaceManager:
    """Manages project workspaces for organized code generation."""
    
    def __init__(self, base_dir: str = "workspaces"):
        """Initialize the workspace manager.
        
        Args:
            base_dir: Base directory for all workspaces
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.current_workspace: Optional[Path] = None
    
    def create_workspace(self, name: str, overwrite: bool = False) -> Path:
        """Create a new workspace directory.
        
        Args:
            name: Workspace name (will be sanitized)
            overwrite: Whether to overwrite existing workspace
            
        Returns:
            Path to workspace directory
        """
        # Sanitize name: remove special chars, lowercase, replace spaces
        safe_name = name.lower().replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        
        # Add timestamp if workspace exists and overwrite=False
        workspace_path = self.base_dir / safe_name
        if workspace_path.exists() and not overwrite:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            workspace_path = self.base_dir / f"{safe_name}_{timestamp}"
        
        workspace_path.mkdir(parents=True, exist_ok=overwrite)
        self.current_workspace = workspace_path
        
        # Create standard subdirectories
        (workspace_path / "src").mkdir(exist_ok=True)
        (workspace_path / "tests").mkdir(exist_ok=True)
        (workspace_path / "docs").mkdir(exist_ok=True)
        
        return workspace_path
    
    def use_workspace(self, name: str) -> Optional[Path]:
        """Use an existing workspace.
        
        Args:
            name: Workspace name to use
            
        Returns:
            Path to workspace or None if not found
        """
        workspace_path = self.base_dir / name
        if not workspace_path.exists():
            # Try to find with glob pattern
            matches = list(self.base_dir.glob(f"{name}*"))
            if not matches:
                return None
            workspace_path = matches[0]
        
        self.current_workspace = workspace_path
        return workspace_path
    
    def list_workspaces(self) -> list[str]:
        """List all available workspaces.
        
        Returns:
            List of workspace names
        """
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]
    
    def get_workspace_path(self, relative_path: str = "") -> Path:
        """Get absolute path within current workspace.
        
        Args:
            relative_path: Path relative to workspace root
            
        Returns:
            Absolute path
            
        Raises:
            ValueError: If no workspace is selected
        """
        if not self.current_workspace:
            raise ValueError("No workspace selected. Call create_workspace() or use_workspace() first")
        
        return self.current_workspace / relative_path
    
    def workspace_info(self) -> dict:
        """Get info about current workspace.
        
        Returns:
            Dictionary containing workspace metadata
        """
        if not self.current_workspace:
            return {"name": None, "path": None, "files": [], "file_count": 0}
        
        files = []
        for path in self.current_workspace.rglob("*"):
            if path.is_file():
                files.append(str(path.relative_to(self.current_workspace)))
        
        return {
            "name": self.current_workspace.name,
            "path": str(self.current_workspace),
            "files": files,
            "file_count": len(files)
        }
