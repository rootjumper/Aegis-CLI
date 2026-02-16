"""Python tool for Aegis-CLI.

Provides Python-specific operations like imports analysis, linting, and formatting.
"""

import ast
import asyncio
from typing import Any

from aegis.tools.base_tool import Tool, ToolResult


class PythonTool(Tool):
    """Tool for Python-specific operations.
    
    Provides capabilities for analyzing imports, running linters,
    checking type hints, and code formatting.
    """
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "python"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "Python-specific operations: imports, linting, type checking, formatting"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "analyze_imports", "lint", "type_check",
                        "format_check", "parse_syntax", "get_functions",
                        "get_classes"
                    ],
                    "description": "Python action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "fix": {
                    "type": "boolean",
                    "description": "Apply fixes automatically",
                    "default": False
                }
            },
            "required": ["action", "path"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the Python operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult containing operation results
        """
        action = kwargs.get("action")
        path = kwargs.get("path", "")
        
        if not path:
            return ToolResult(success=False, error="Path is required")
        
        try:
            if action == "analyze_imports":
                return await self._analyze_imports(path)
            elif action == "lint":
                return await self._lint(path)
            elif action == "type_check":
                return await self._type_check(path)
            elif action == "format_check":
                return await self._format_check(path, kwargs.get("fix", False))
            elif action == "parse_syntax":
                return await self._parse_syntax(path)
            elif action == "get_functions":
                return await self._get_functions(path)
            elif action == "get_classes":
                return await self._get_classes(path)
            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _run_command(self, args: list[str]) -> tuple[bool, str, str]:
        """Run a command and return output.
        
        Args:
            args: Command arguments
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60
            )
            
            success = process.returncode == 0
            
            return (
                success,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace")
            )
        except Exception as e:
            return False, "", str(e)
    
    async def _analyze_imports(self, path: str) -> ToolResult:
        """Analyze imports in a Python file.
        
        Args:
            path: Python file path
            
        Returns:
            ToolResult with import analysis
        """
        import os
        
        if not os.path.exists(path):
            return ToolResult(success=False, error=f"File not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            
            imports = {
                "standard_library": [],
                "third_party": [],
                "local": [],
                "from_imports": []
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports["third_party"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    imports["from_imports"].append({
                        "module": module,
                        "names": [alias.name for alias in node.names]
                    })
            
            return ToolResult(
                success=True,
                data={
                    "imports": imports,
                    "total": (
                        len(imports["standard_library"]) +
                        len(imports["third_party"]) +
                        len(imports["local"]) +
                        len(imports["from_imports"])
                    )
                }
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                error=f"Syntax error in file: {e}"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _lint(self, path: str) -> ToolResult:
        """Run pylint on Python code.
        
        Args:
            path: File or directory path
            
        Returns:
            ToolResult with linting results
        """
        args = ["python", "-m", "pylint", path, "--output-format=json"]
        
        success, stdout, stderr = await self._run_command(args)
        
        try:
            import json
            issues = json.loads(stdout) if stdout else []
        except json.JSONDecodeError:
            issues = []
        
        return ToolResult(
            success=len(issues) == 0,
            data={
                "issues": issues,
                "issue_count": len(issues),
                "passed": len(issues) == 0,
                "raw_output": stderr if not success else ""
            }
        )
    
    async def _type_check(self, path: str) -> ToolResult:
        """Run mypy type checking.
        
        Args:
            path: File or directory path
            
        Returns:
            ToolResult with type checking results
        """
        args = ["python", "-m", "mypy", path, "--no-error-summary"]
        
        success, stdout, stderr = await self._run_command(args)
        
        # Parse mypy output
        errors = []
        if stdout:
            for line in stdout.split("\n"):
                if ": error:" in line:
                    errors.append(line)
        
        return ToolResult(
            success=success and len(errors) == 0,
            data={
                "errors": errors,
                "error_count": len(errors),
                "passed": success and len(errors) == 0,
                "output": stdout
            }
        )
    
    async def _format_check(self, path: str, fix: bool) -> ToolResult:
        """Check or fix Python code formatting.
        
        Args:
            path: File or directory path
            fix: Apply fixes automatically
            
        Returns:
            ToolResult with formatting results
        """
        # Use black for formatting
        args = ["python", "-m", "black"]
        
        if not fix:
            args.append("--check")
        
        args.append(path)
        
        success, stdout, stderr = await self._run_command(args)
        
        return ToolResult(
            success=success,
            data={
                "formatted": fix,
                "needs_formatting": not success,
                "output": stdout,
                "errors": stderr
            }
        )
    
    async def _parse_syntax(self, path: str) -> ToolResult:
        """Parse Python file and check syntax.
        
        Args:
            path: Python file path
            
        Returns:
            ToolResult with syntax check results
        """
        import os
        
        if not os.path.exists(path):
            return ToolResult(success=False, error=f"File not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            
            tree = ast.parse(code, filename=path)
            
            return ToolResult(
                success=True,
                data={
                    "valid": True,
                    "ast_nodes": len(list(ast.walk(tree))),
                    "message": "Syntax is valid"
                }
            )
        except SyntaxError as e:
            return ToolResult(
                success=False,
                error=f"Syntax error at line {e.lineno}: {e.msg}"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _get_functions(self, path: str) -> ToolResult:
        """Extract all function definitions from a Python file.
        
        Args:
            path: Python file path
            
        Returns:
            ToolResult with function list
        """
        import os
        
        if not os.path.exists(path):
            return ToolResult(success=False, error=f"File not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            
            functions = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Extract function info
                    args = [arg.arg for arg in node.args.args]
                    
                    # Get docstring
                    docstring = ast.get_docstring(node)
                    
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "arguments": args,
                        "docstring": docstring,
                        "is_async": isinstance(node, ast.AsyncFunctionDef)
                    })
            
            return ToolResult(
                success=True,
                data={
                    "functions": functions,
                    "count": len(functions)
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    async def _get_classes(self, path: str) -> ToolResult:
        """Extract all class definitions from a Python file.
        
        Args:
            path: Python file path
            
        Returns:
            ToolResult with class list
        """
        import os
        
        if not os.path.exists(path):
            return ToolResult(success=False, error=f"File not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            
            classes = []
            
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    # Extract class info
                    bases = [self._get_base_name(base) for base in node.bases]
                    
                    # Get methods
                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append(item.name)
                    
                    # Get docstring
                    docstring = ast.get_docstring(node)
                    
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                        "bases": bases,
                        "methods": methods,
                        "docstring": docstring
                    })
            
            return ToolResult(
                success=True,
                data={
                    "classes": classes,
                    "count": len(classes)
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _get_base_name(self, node: ast.expr) -> str:
        """Get base class name from AST node.
        
        Args:
            node: AST node
            
        Returns:
            Base class name
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_base_name(node.value)}.{node.attr}"
        else:
            return "Unknown"
