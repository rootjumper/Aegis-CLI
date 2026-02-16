"""Testing tool for Aegis-CLI.

Provides test execution, coverage analysis, and test reporting capabilities.
"""

import asyncio
import json
from typing import Any

from aegis.tools.base_tool import Tool, ToolResult


class TestingTool(Tool):
    """Tool for test execution and analysis.
    
    Provides capabilities for running tests, analyzing coverage,
    and generating test reports.
    """
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return "testing"
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return "Test execution, coverage analysis, and test reporting"
    
    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Get the JSON schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "run_tests", "run_coverage", "list_tests",
                        "run_specific", "validate_tests"
                    ],
                    "description": "Testing action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "Test file or directory path",
                    "default": "tests/"
                },
                "test_name": {
                    "type": "string",
                    "description": "Specific test name to run"
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Enable verbose output",
                    "default": False
                },
                "coverage_threshold": {
                    "type": "integer",
                    "description": "Minimum coverage percentage",
                    "default": 80
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the testing operation.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            ToolResult containing operation results
        """
        action = kwargs.get("action")
        
        try:
            if action == "run_tests":
                return await self._run_tests(
                    kwargs.get("path", "tests/"),
                    kwargs.get("verbose", False)
                )
            elif action == "run_coverage":
                return await self._run_coverage(
                    kwargs.get("path", "tests/"),
                    kwargs.get("coverage_threshold", 80)
                )
            elif action == "list_tests":
                return await self._list_tests(kwargs.get("path", "tests/"))
            elif action == "run_specific":
                return await self._run_specific(
                    kwargs.get("test_name", ""),
                    kwargs.get("verbose", False)
                )
            elif action == "validate_tests":
                return await self._validate_tests(kwargs.get("path", "tests/"))
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
                timeout=300  # 5 minute timeout
            )
            
            success = process.returncode == 0
            
            return (
                success,
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace")
            )
        except asyncio.TimeoutError:
            return False, "", "Test execution timed out after 5 minutes"
        except Exception as e:
            return False, "", str(e)
    
    async def _run_tests(self, path: str, verbose: bool) -> ToolResult:
        """Run tests using pytest.
        
        Args:
            path: Test path
            verbose: Enable verbose output
            
        Returns:
            ToolResult with test results
        """
        args = ["python", "-m", "pytest", path, "-v" if verbose else "-q"]
        
        success, stdout, stderr = await self._run_command(args)
        
        # Parse test results
        results = self._parse_pytest_output(stdout)
        
        return ToolResult(
            success=success,
            data={
                "passed": success,
                "output": stdout,
                "errors": stderr,
                "summary": results
            }
        )
    
    def _parse_pytest_output(self, output: str) -> dict[str, Any]:
        """Parse pytest output for summary.
        
        Args:
            output: pytest output
            
        Returns:
            Dictionary with parsed results
        """
        lines = output.split("\n")
        
        # Look for the summary line
        for line in lines:
            if "passed" in line or "failed" in line:
                # Extract counts
                import re
                passed = re.search(r"(\d+) passed", line)
                failed = re.search(r"(\d+) failed", line)
                skipped = re.search(r"(\d+) skipped", line)
                
                return {
                    "passed": int(passed.group(1)) if passed else 0,
                    "failed": int(failed.group(1)) if failed else 0,
                    "skipped": int(skipped.group(1)) if skipped else 0
                }
        
        return {"passed": 0, "failed": 0, "skipped": 0}
    
    async def _run_coverage(
        self,
        path: str,
        threshold: int
    ) -> ToolResult:
        """Run tests with coverage analysis.
        
        Args:
            path: Test path
            threshold: Minimum coverage percentage
            
        Returns:
            ToolResult with coverage results
        """
        args = [
            "python", "-m", "pytest",
            path,
            "--cov=aegis",
            f"--cov-fail-under={threshold}",
            "--cov-report=term-missing"
        ]
        
        success, stdout, stderr = await self._run_command(args)
        
        # Parse coverage percentage
        coverage_pct = self._parse_coverage(stdout)
        
        return ToolResult(
            success=success and coverage_pct >= threshold,
            data={
                "coverage_percentage": coverage_pct,
                "threshold": threshold,
                "passed_threshold": coverage_pct >= threshold,
                "output": stdout,
                "errors": stderr
            }
        )
    
    def _parse_coverage(self, output: str) -> float:
        """Parse coverage percentage from output.
        
        Args:
            output: Coverage output
            
        Returns:
            Coverage percentage
        """
        import re
        
        # Look for "TOTAL ... XX%"
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if match:
            return float(match.group(1))
        
        return 0.0
    
    async def _list_tests(self, path: str) -> ToolResult:
        """List all available tests.
        
        Args:
            path: Test directory path
            
        Returns:
            ToolResult with test list
        """
        args = ["python", "-m", "pytest", path, "--collect-only", "-q"]
        
        success, stdout, stderr = await self._run_command(args)
        
        if not success:
            return ToolResult(
                success=False,
                error=stderr or "Failed to list tests"
            )
        
        # Parse test names from output
        tests = []
        for line in stdout.split("\n"):
            if "::" in line and not line.startswith(" "):
                tests.append(line.strip())
        
        return ToolResult(
            success=True,
            data={
                "tests": tests,
                "count": len(tests)
            }
        )
    
    async def _run_specific(self, test_name: str, verbose: bool) -> ToolResult:
        """Run a specific test.
        
        Args:
            test_name: Test name or pattern
            verbose: Enable verbose output
            
        Returns:
            ToolResult with test results
        """
        if not test_name:
            return ToolResult(success=False, error="Test name is required")
        
        args = [
            "python", "-m", "pytest",
            "-k", test_name,
            "-v" if verbose else "-q"
        ]
        
        success, stdout, stderr = await self._run_command(args)
        
        return ToolResult(
            success=success,
            data={
                "passed": success,
                "output": stdout,
                "errors": stderr
            }
        )
    
    async def _validate_tests(self, path: str) -> ToolResult:
        """Validate test structure and naming.
        
        Args:
            path: Test directory path
            
        Returns:
            ToolResult with validation results
        """
        import os
        
        issues = []
        test_files = []
        
        # Check test directory exists
        if not os.path.exists(path):
            return ToolResult(
                success=False,
                error=f"Test directory not found: {path}"
            )
        
        # Find all test files
        for root, _, files in os.walk(path):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    test_files.append(os.path.join(root, file))
        
        if not test_files:
            issues.append(f"No test files found in {path}")
        
        # Basic validation
        for test_file in test_files:
            try:
                with open(test_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # Check for basic test structure
                    if "import pytest" not in content and "from pytest" not in content:
                        issues.append(f"{test_file}: Missing pytest import")
                    
                    # Check for test functions
                    if "def test_" not in content:
                        issues.append(f"{test_file}: No test functions found")
            except Exception as e:
                issues.append(f"{test_file}: Error reading file - {e}")
        
        return ToolResult(
            success=len(issues) == 0,
            data={
                "test_files": test_files,
                "test_count": len(test_files),
                "issues": issues,
                "valid": len(issues) == 0
            }
        )
