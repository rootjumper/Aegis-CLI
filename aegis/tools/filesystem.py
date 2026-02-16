"""Filesystem tool for Aegis-CLI.

Provides file operations including reading, listing, searching, and smart patching.
"""

import os
import re
import difflib
from pathlib import Path
from typing import Any
import chardet

from aegis.tools.base_tool import Tool, ToolResult


class FileSystemTool(Tool):
    """Tool for file system operations.
    
    Provides capabilities for reading files, listing directories,
    searching content, and applying surgical edits.
    """
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "filesystem"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "File system operations: read, list, search, and smart patch"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "read_file", "write_file", "list_directory", 
                        "search_content", "smart_patch", "delete_file",
                        "create_directory", "file_exists"
                    ],
                    "description": "Action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "pattern": {
                    "type": "string",
                    "description": "Search pattern or glob pattern"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write_file)"
                },
                "changes": {
                    "type": "array",
                    "description": "List of changes for smart_patch"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the file system operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult containing operation results
        """
        action = kwargs.get("action")
        
        try:
            if action == "read_file":
                return await self._read_file(kwargs.get("path", ""))
            elif action == "write_file":
                return await self._write_file(
                    kwargs.get("path", ""),
                    kwargs.get("content", "")
                )
            elif action == "list_directory":
                return await self._list_directory(
                    kwargs.get("path", "."),
                    kwargs.get("pattern", "*")
                )
            elif action == "search_content":
                return await self._search_content(
                    kwargs.get("pattern", ""),
                    kwargs.get("path", ".")
                )
            elif action == "smart_patch":
                return await self._smart_patch(
                    kwargs.get("path", ""),
                    kwargs.get("changes", [])
                )
            elif action == "delete_file":
                return await self._delete_file(kwargs.get("path", ""))
            elif action == "create_directory":
                return await self._create_directory(kwargs.get("path", ""))
            elif action == "file_exists":
                return await self._file_exists(kwargs.get("path", ""))
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _read_file(self, path: str) -> ToolResult:
        """Read a file with encoding detection.
        
        Args:
            path: File path
            
        Returns:
            ToolResult with file content
        """
        if not path or not os.path.exists(path):
            return ToolResult(success=False, error=f"File not found: {path}")
        
        # Detect encoding
        with open(path, "rb") as f:
            raw_data = f.read()
            detected = chardet.detect(raw_data)
            encoding = detected.get("encoding", "utf-8")
        
        # Read with detected encoding
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            return ToolResult(success=True, data=content)
        except Exception as e:
            return ToolResult(success=False, error=f"Error reading file: {e}")
    
    async def _list_directory(self, path: str, pattern: str) -> ToolResult:
        """List directory contents with optional pattern matching.
        
        Args:
            path: Directory path
            pattern: Glob pattern
            
        Returns:
            ToolResult with list of files
        """
        if not os.path.exists(path):
            return ToolResult(success=False, error=f"Directory not found: {path}")
        
        try:
            p = Path(path)
            if pattern == "*":
                files = [str(f.relative_to(p)) for f in p.rglob("*") if f.is_file()]
            else:
                files = [str(f.relative_to(p)) for f in p.rglob(pattern) if f.is_file()]
            
            return ToolResult(success=True, data=files)
        except Exception as e:
            return ToolResult(success=False, error=f"Error listing directory: {e}")
    
    async def _search_content(self, pattern: str, path: str) -> ToolResult:
        """Search for content in files (grep-like).
        
        Args:
            pattern: Regular expression pattern
            path: Starting directory path
            
        Returns:
            ToolResult with list of matches
        """
        if not pattern:
            return ToolResult(success=False, error="Pattern is required")
        
        try:
            matches = []
            regex = re.compile(pattern)
            
            for root, _, files in os.walk(path):
                for file in files:
                    # Skip binary and hidden files
                    if file.startswith(".") or file.endswith((".pyc", ".so", ".db")):
                        continue
                    
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append({
                                        "file": file_path,
                                        "line": line_num,
                                        "content": line.strip()
                                    })
                    except Exception:
                        # Skip files that can't be read
                        continue
            
            return ToolResult(success=True, data=matches)
        except Exception as e:
            return ToolResult(success=False, error=f"Error searching: {e}")
    
    async def _smart_patch(self, file_path: str, changes: list[dict[str, Any]]) -> ToolResult:
        """Apply surgical edits to a file.
        
        Args:
            file_path: File to patch
            changes: List of change dictionaries
            
        Returns:
            ToolResult with patched content
        """
        if not file_path or not os.path.exists(file_path):
            return ToolResult(success=False, error=f"File not found: {file_path}")
        
        try:
            # Read current content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines(keepends=True)
            
            # Apply changes
            for change in changes:
                action = change.get("action")
                
                if action == "replace":
                    old = change.get("old", "")
                    new = change.get("new", "")
                    if old in content:
                        content = content.replace(old, new, 1)
                    else:
                        return ToolResult(
                            success=False,
                            error=f"Pattern not found for replace: {old[:50]}"
                        )
                
                elif action == "insert_after":
                    anchor = change.get("anchor", "")
                    insert_content = change.get("content", "")
                    if anchor in content:
                        parts = content.split(anchor, 1)
                        content = parts[0] + anchor + "\n" + insert_content + parts[1]
                    else:
                        return ToolResult(
                            success=False,
                            error=f"Anchor not found for insert: {anchor[:50]}"
                        )
                
                elif action == "delete":
                    pattern = change.get("pattern", "")
                    content = re.sub(pattern, "", content, count=1)
            
            # Write back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(
                success=True,
                data={"message": "File patched successfully", "path": file_path}
            )
        
        except Exception as e:
            return ToolResult(success=False, error=f"Error patching file: {e}")
    
    async def _write_file(self, path: str, content: str) -> ToolResult:
        """Write content to a file.
        
        Args:
            path: File path
            content: Content to write
            
        Returns:
            ToolResult with success status
        """
        if not path:
            return ToolResult(success=False, error="Path is required")
        
        try:
            # Create parent directories if they don't exist
            parent_dir = Path(path).parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            # Write content
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(
                success=True,
                data={"message": f"File written successfully: {path}", "path": path}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error writing file: {e}")
    
    async def _delete_file(self, path: str) -> ToolResult:
        """Delete a file.
        
        Args:
            path: File path
            
        Returns:
            ToolResult with success status
        """
        if not path:
            return ToolResult(success=False, error="Path is required")
        
        if not os.path.exists(path):
            return ToolResult(success=False, error=f"File not found: {path}")
        
        try:
            if os.path.isfile(path):
                os.remove(path)
                return ToolResult(
                    success=True,
                    data={"message": f"File deleted successfully: {path}"}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {path}"
                )
        except Exception as e:
            return ToolResult(success=False, error=f"Error deleting file: {e}")
    
    async def _create_directory(self, path: str) -> ToolResult:
        """Create a directory.
        
        Args:
            path: Directory path
            
        Returns:
            ToolResult with success status
        """
        if not path:
            return ToolResult(success=False, error="Path is required")
        
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return ToolResult(
                success=True,
                data={"message": f"Directory created successfully: {path}"}
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error creating directory: {e}")
    
    async def _file_exists(self, path: str) -> ToolResult:
        """Check if a file or directory exists.
        
        Args:
            path: File or directory path
            
        Returns:
            ToolResult with existence status
        """
        if not path:
            return ToolResult(success=False, error="Path is required")
        
        exists = os.path.exists(path)
        is_file = os.path.isfile(path) if exists else False
        is_dir = os.path.isdir(path) if exists else False
        
        return ToolResult(
            success=True,
            data={
                "exists": exists,
                "is_file": is_file,
                "is_directory": is_dir,
                "path": path
            }
        )
