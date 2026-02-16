"""Integration tests for filesystem tool."""

import os
import tempfile
import pytest
from pathlib import Path

from aegis.tools.filesystem import FileSystemTool


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def filesystem_tool():
    """Create a FileSystemTool instance."""
    return FileSystemTool()


@pytest.mark.asyncio
async def test_write_and_read_file(filesystem_tool, temp_dir):
    """Test writing and reading a file."""
    file_path = os.path.join(temp_dir, "test.txt")
    content = "Hello, World!"
    
    # Write file
    result = await filesystem_tool.execute(
        action="write_file",
        path=file_path,
        content=content
    )
    
    assert result.success is True
    assert os.path.exists(file_path)
    
    # Read file
    result = await filesystem_tool.execute(
        action="read_file",
        path=file_path
    )
    
    assert result.success is True
    assert result.data == content


@pytest.mark.asyncio
async def test_delete_file(filesystem_tool, temp_dir):
    """Test deleting a file."""
    file_path = os.path.join(temp_dir, "delete_me.txt")
    
    # Create file
    with open(file_path, "w") as f:
        f.write("test")
    
    # Delete file
    result = await filesystem_tool.execute(
        action="delete_file",
        path=file_path
    )
    
    assert result.success is True
    assert not os.path.exists(file_path)


@pytest.mark.asyncio
async def test_create_directory(filesystem_tool, temp_dir):
    """Test creating a directory."""
    dir_path = os.path.join(temp_dir, "subdir", "nested")
    
    result = await filesystem_tool.execute(
        action="create_directory",
        path=dir_path
    )
    
    assert result.success is True
    assert os.path.exists(dir_path)
    assert os.path.isdir(dir_path)


@pytest.mark.asyncio
async def test_file_exists(filesystem_tool, temp_dir):
    """Test checking if a file exists."""
    file_path = os.path.join(temp_dir, "exists.txt")
    
    # Check non-existent file
    result = await filesystem_tool.execute(
        action="file_exists",
        path=file_path
    )
    
    assert result.success is True
    assert result.data["exists"] is False
    
    # Create file
    with open(file_path, "w") as f:
        f.write("test")
    
    # Check existing file
    result = await filesystem_tool.execute(
        action="file_exists",
        path=file_path
    )
    
    assert result.success is True
    assert result.data["exists"] is True
    assert result.data["is_file"] is True


@pytest.mark.asyncio
async def test_list_directory(filesystem_tool, temp_dir):
    """Test listing directory contents."""
    # Create some files
    Path(temp_dir, "file1.txt").touch()
    Path(temp_dir, "file2.py").touch()
    Path(temp_dir, "subdir").mkdir()
    Path(temp_dir, "subdir", "file3.txt").touch()
    
    result = await filesystem_tool.execute(
        action="list_directory",
        path=temp_dir,
        pattern="*.txt"
    )
    
    assert result.success is True
    assert len(result.data) >= 2  # file1.txt and subdir/file3.txt


@pytest.mark.asyncio
async def test_search_content(filesystem_tool, temp_dir):
    """Test searching for content in files."""
    # Create test files
    file1 = os.path.join(temp_dir, "file1.txt")
    file2 = os.path.join(temp_dir, "file2.txt")
    
    with open(file1, "w") as f:
        f.write("Hello World\n")
    
    with open(file2, "w") as f:
        f.write("Goodbye World\n")
    
    result = await filesystem_tool.execute(
        action="search_content",
        pattern="World",
        path=temp_dir
    )
    
    assert result.success is True
    assert len(result.data) >= 2  # Found in both files


@pytest.mark.asyncio
async def test_smart_patch(filesystem_tool, temp_dir):
    """Test smart patching a file."""
    file_path = os.path.join(temp_dir, "patch_me.py")
    
    # Create test file
    with open(file_path, "w") as f:
        f.write("def old_function():\n    pass\n")
    
    # Apply patch
    result = await filesystem_tool.execute(
        action="smart_patch",
        path=file_path,
        changes=[
            {
                "action": "replace",
                "old": "old_function",
                "new": "new_function"
            }
        ]
    )
    
    assert result.success is True
    
    # Verify patch was applied
    with open(file_path, "r") as f:
        content = f.read()
        assert "new_function" in content
        assert "old_function" not in content


@pytest.mark.asyncio
async def test_write_file_creates_parent_dirs(filesystem_tool, temp_dir):
    """Test that write_file creates parent directories."""
    file_path = os.path.join(temp_dir, "nested", "dirs", "file.txt")
    
    result = await filesystem_tool.execute(
        action="write_file",
        path=file_path,
        content="test"
    )
    
    assert result.success is True
    assert os.path.exists(file_path)


@pytest.mark.asyncio
async def test_read_nonexistent_file(filesystem_tool):
    """Test reading a non-existent file."""
    result = await filesystem_tool.execute(
        action="read_file",
        path="/nonexistent/file.txt"
    )
    
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_file(filesystem_tool):
    """Test deleting a non-existent file."""
    result = await filesystem_tool.execute(
        action="delete_file",
        path="/nonexistent/file.txt"
    )
    
    assert result.success is False
    assert "not found" in result.error.lower()
