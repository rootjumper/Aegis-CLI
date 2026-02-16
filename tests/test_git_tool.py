"""Tests for Git tool."""

import os
import tempfile
import pytest
from pathlib import Path

from aegis.tools.git import GitTool


@pytest.fixture
def git_tool():
    """Create a GitTool instance."""
    return GitTool()


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        os.system(f"cd {tmpdir} && git init && git config user.email 'test@test.com' && git config user.name 'Test User'")
        yield tmpdir


def test_git_tool_creation(git_tool):
    """Test creating a GitTool."""
    assert git_tool.name == "git"
    assert "git" in git_tool.description.lower()


def test_git_tool_schema(git_tool):
    """Test GitTool parameter schema."""
    schema = git_tool.parameters_schema
    
    assert "properties" in schema
    assert "action" in schema["properties"]
    assert schema["required"] == ["action"]
    assert "status" in schema["properties"]["action"]["enum"]


@pytest.mark.asyncio
async def test_git_status(git_tool, temp_git_repo):
    """Test git status action."""
    # Change to temp repo directory
    original_dir = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        # Create a test file
        test_file = Path(temp_git_repo, "test.txt")
        test_file.write_text("test content")
        
        result = await git_tool.execute(action="status")
        
        assert result.success is True
        assert result.data is not None
        assert "status" in result.data
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_git_current_branch(git_tool, temp_git_repo):
    """Test getting current branch."""
    original_dir = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        result = await git_tool.execute(action="current_branch")
        
        assert result.success is True
        assert "branch" in result.data
        # Should be 'main' or 'master' for a new repo
        assert result.data["branch"] in ["main", "master", ""]
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_git_list_branches(git_tool, temp_git_repo):
    """Test listing branches."""
    original_dir = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        result = await git_tool.execute(action="list_branches")
        
        assert result.success is True
        assert "branches" in result.data
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_git_diff(git_tool, temp_git_repo):
    """Test git diff."""
    original_dir = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        # Create and commit a file first
        test_file = Path(temp_git_repo, "test.txt")
        test_file.write_text("initial content")
        os.system(f"cd {temp_git_repo} && git add test.txt && git commit -m 'Initial'")
        
        # Modify the file
        test_file.write_text("modified content")
        
        result = await git_tool.execute(action="diff")
        
        assert result.success is True
        assert "diff" in result.data
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_git_log(git_tool, temp_git_repo):
    """Test git log."""
    original_dir = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        # Create initial commit
        test_file = Path(temp_git_repo, "test.txt")
        test_file.write_text("test")
        os.system(f"cd {temp_git_repo} && git add test.txt && git commit -m 'Initial commit'")
        
        result = await git_tool.execute(action="log", limit=5)
        
        assert result.success is True
        assert "commits" in result.data
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_git_add(git_tool, temp_git_repo):
    """Test git add."""
    original_dir = os.getcwd()
    os.chdir(temp_git_repo)
    
    try:
        # Create a file
        test_file = Path(temp_git_repo, "test.txt")
        test_file.write_text("test")
        
        result = await git_tool.execute(action="add", path="test.txt")
        
        assert result.success is True
        assert "message" in result.data
    finally:
        os.chdir(original_dir)


@pytest.mark.asyncio
async def test_git_invalid_action(git_tool):
    """Test invalid git action."""
    result = await git_tool.execute(action="invalid_action")
    
    assert result.success is False
    assert "Unknown action" in result.error
