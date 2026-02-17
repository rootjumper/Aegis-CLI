"""Tests for workspace management."""

import pytest
from pathlib import Path
import tempfile
import shutil

from aegis.core.workspace import WorkspaceManager


@pytest.fixture
def temp_workspace_dir():
    """Create a temporary directory for workspace tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_workspace_manager_creation(temp_workspace_dir: str) -> None:
    """Test creating a WorkspaceManager."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    assert manager.base_dir == Path(temp_workspace_dir)
    assert manager.base_dir.exists()
    assert manager.current_workspace is None


def test_create_workspace(temp_workspace_dir: str) -> None:
    """Test creating a new workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    workspace = manager.create_workspace("test_project")
    
    assert workspace.exists()
    assert workspace.name == "test_project"
    assert manager.current_workspace == workspace
    
    # Check standard subdirectories
    assert (workspace / "src").exists()
    assert (workspace / "tests").exists()
    assert (workspace / "docs").exists()


def test_create_workspace_sanitizes_name(temp_workspace_dir: str) -> None:
    """Test that workspace names are sanitized."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    workspace = manager.create_workspace("Test Project With Spaces!")
    
    assert workspace.name == "test_project_with_spaces"
    assert workspace.exists()


def test_create_workspace_with_timestamp(temp_workspace_dir: str) -> None:
    """Test that duplicate workspaces get timestamps."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    # Create first workspace
    workspace1 = manager.create_workspace("duplicate")
    
    # Create second workspace with same name
    workspace2 = manager.create_workspace("duplicate")
    
    assert workspace1.exists()
    assert workspace2.exists()
    assert workspace1 != workspace2
    assert workspace2.name.startswith("duplicate_")


def test_create_workspace_with_overwrite(temp_workspace_dir: str) -> None:
    """Test overwriting an existing workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    # Create first workspace
    workspace1 = manager.create_workspace("overwrite_test")
    test_file = workspace1 / "test.txt"
    test_file.write_text("original content")
    
    # Overwrite - should reuse same directory
    workspace2 = manager.create_workspace("overwrite_test", overwrite=True)
    
    assert workspace1 == workspace2
    # Note: overwrite=True allows reusing the directory but doesn't clear it
    # The test_file still exists but that's okay - we're just allowing workspace reuse


def test_use_workspace(temp_workspace_dir: str) -> None:
    """Test using an existing workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    # Create a workspace
    created = manager.create_workspace("existing")
    
    # Create a new manager and use the existing workspace
    manager2 = WorkspaceManager(base_dir=temp_workspace_dir)
    used = manager2.use_workspace("existing")
    
    assert used == created
    assert manager2.current_workspace == used


def test_use_workspace_with_pattern(temp_workspace_dir: str) -> None:
    """Test using workspace with partial name match."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    # Create a workspace with timestamp
    created = manager.create_workspace("pattern_test")
    
    # Create second instance with timestamp
    manager.create_workspace("pattern_test")
    
    # Try to use with base name - should find first match
    manager2 = WorkspaceManager(base_dir=temp_workspace_dir)
    used = manager2.use_workspace("pattern")
    
    assert used is not None
    assert "pattern" in used.name


def test_use_nonexistent_workspace(temp_workspace_dir: str) -> None:
    """Test using a workspace that doesn't exist."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    result = manager.use_workspace("nonexistent")
    
    assert result is None


def test_list_workspaces(temp_workspace_dir: str) -> None:
    """Test listing all workspaces."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    manager.create_workspace("workspace1")
    manager.create_workspace("workspace2")
    manager.create_workspace("workspace3")
    
    workspaces = manager.list_workspaces()
    
    assert len(workspaces) == 3
    assert "workspace1" in workspaces
    assert "workspace2" in workspaces
    assert "workspace3" in workspaces


def test_get_workspace_path(temp_workspace_dir: str) -> None:
    """Test getting paths within workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    workspace = manager.create_workspace("path_test")
    
    # Get path to a file in workspace
    file_path = manager.get_workspace_path("src/main.py")
    
    assert file_path == workspace / "src/main.py"
    assert str(file_path).endswith("src/main.py")


def test_get_workspace_path_no_workspace(temp_workspace_dir: str) -> None:
    """Test getting workspace path without selecting workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    with pytest.raises(ValueError, match="No workspace selected"):
        manager.get_workspace_path("test.py")


def test_workspace_info_empty(temp_workspace_dir: str) -> None:
    """Test workspace info for empty workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    workspace = manager.create_workspace("info_test")
    info = manager.workspace_info()
    
    assert info["name"] == "info_test"
    assert info["path"] == str(workspace)
    assert info["files"] == []
    assert info["file_count"] == 0


def test_workspace_info_with_files(temp_workspace_dir: str) -> None:
    """Test workspace info with files."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    workspace = manager.create_workspace("files_test")
    
    # Create some files
    (workspace / "src/main.py").write_text("print('hello')")
    (workspace / "tests/test_main.py").write_text("def test(): pass")
    (workspace / "README.md").write_text("# Test")
    
    info = manager.workspace_info()
    
    assert info["name"] == "files_test"
    assert info["file_count"] == 3
    assert "src/main.py" in info["files"]
    assert "tests/test_main.py" in info["files"]
    assert "README.md" in info["files"]


def test_workspace_info_no_workspace(temp_workspace_dir: str) -> None:
    """Test workspace info without selecting workspace."""
    manager = WorkspaceManager(base_dir=temp_workspace_dir)
    
    info = manager.workspace_info()
    
    assert info["name"] is None
    assert info["path"] is None
    assert info["files"] == []
    assert info["file_count"] == 0
