"""Critic agent for code review.

Reviews code for quality, security, and best practices.
"""

import re
from typing import Any
from pydantic_ai.models import Model

from aegis.agents.base import BaseAgent, AgentTask, AgentResponse
from aegis.tools.registry import get_registry


class CriticAgent(BaseAgent):
    """Agent specialized in code review.
    
    Reviews code for:
    - PEP8 compliance
    - Type safety
    - Security vulnerabilities
    - Logic soundness
    """
    
    # Security patterns to check
    SECURITY_PATTERNS = [
        (r"\beval\s*\(", "Use of eval() is dangerous"),
        (r"\bexec\s*\(", "Use of exec() is dangerous"),
        (r"password\s*=\s*['\"][^'\"]+['\"]", "Hardcoded password detected"),
        (r"api_key\s*=\s*['\"][^'\"]+['\"]", "Hardcoded API key detected"),
        (r"secret\s*=\s*['\"][^'\"]+['\"]", "Hardcoded secret detected"),
    ]
    
    def __init__(self, model: Model | None = None) -> None:
        """Initialize the critic agent.
        
        Args:
            model: Optional PydanticAI Model to use
        """
        super().__init__("critic", model=model)
        self.registry = get_registry()
    
    async def process(self, task: AgentTask) -> AgentResponse:
        """Process a code review task.
        
        Args:
            task: Task to process
            
        Returns:
            AgentResponse with review results
        """
        try:
            # Get code to review
            code = task.payload.get("code", "")
            file_path = task.payload.get("file_path", "")
            
            if not code:
                return AgentResponse(
                    status="FAIL",
                    data={},
                    reasoning_trace="No code provided for review",
                    errors=["Missing code in task payload"]
                )
            
            # Perform review checks
            issues = []
            
            # Security checks
            security_issues = self._check_security(code)
            issues.extend(security_issues)
            
            # Basic code quality checks
            quality_issues = self._check_quality(code)
            issues.extend(quality_issues)
            
            # Type hint checks
            type_issues = self._check_type_hints(code)
            issues.extend(type_issues)
            
            # Docstring checks
            doc_issues = self._check_docstrings(code)
            issues.extend(doc_issues)
            
            # Determine status
            if issues:
                # Check if any are critical (security)
                critical = any("security" in issue.lower() or "dangerous" in issue.lower() 
                             for issue in issues)
                
                status = "FAIL" if critical or len(issues) > 5 else "RETRY"
                
                return AgentResponse(
                    status=status,
                    data={"issues": issues},
                    reasoning_trace=f"Found {len(issues)} issues in code review",
                    errors=issues
                )
            
            # No issues found
            return AgentResponse(
                status="SUCCESS",
                data={"message": "Code passed all review checks"},
                reasoning_trace="Code review completed successfully"
            )
        
        except Exception as e:
            return AgentResponse(
                status="FAIL",
                data={},
                reasoning_trace=f"Error during review: {e}",
                errors=[str(e)]
            )
    
    def _check_security(self, code: str) -> list[str]:
        """Check for security vulnerabilities.
        
        Args:
            code: Code to check
            
        Returns:
            List of security issues
        """
        issues = []
        
        for pattern, message in self.SECURITY_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"SECURITY: {message}")
        
        return issues
    
    def _check_quality(self, code: str) -> list[str]:
        """Check basic code quality.
        
        Args:
            code: Code to check
            
        Returns:
            List of quality issues
        """
        issues = []
        
        # Check for bare except
        if re.search(r"except\s*:", code):
            issues.append("QUALITY: Bare except clause found - specify exception types")
        
        # Check for print statements (should use logging)
        if re.search(r"\bprint\s*\(", code):
            issues.append("QUALITY: print() statement found - consider using logging")
        
        # Check line length (rough check)
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line) > 100:
                issues.append(f"QUALITY: Line {i} exceeds 100 characters")
        
        return issues
    
    def _check_type_hints(self, code: str) -> list[str]:
        """Check for type hints.
        
        Args:
            code: Code to check
            
        Returns:
            List of type hint issues
        """
        issues = []
        
        # Find function definitions
        func_pattern = r"def\s+(\w+)\s*\([^)]*\)\s*(?:->)?"
        functions = re.finditer(func_pattern, code)
        
        for match in functions:
            func_def = match.group(0)
            func_name = match.group(1)
            
            # Skip magic methods
            if func_name.startswith("__") and func_name.endswith("__"):
                continue
            
            # Check for return type hint
            if "->" not in func_def:
                issues.append(f"TYPE: Function '{func_name}' missing return type hint")
        
        return issues
    
    def _check_docstrings(self, code: str) -> list[str]:
        """Check for docstrings.
        
        Args:
            code: Code to check
            
        Returns:
            List of docstring issues
        """
        issues = []
        
        # Find function definitions
        func_pattern = r"def\s+(\w+)\s*\([^)]*\).*?(?=\n\s*def|\n\s*class|\Z)"
        functions = re.finditer(func_pattern, code, re.DOTALL)
        
        for match in functions:
            func_body = match.group(0)
            func_name = match.group(1)
            
            # Skip magic methods and private methods
            if func_name.startswith("_"):
                continue
            
            # Check for docstring (triple quotes)
            if '"""' not in func_body and "'''" not in func_body:
                issues.append(f"DOC: Function '{func_name}' missing docstring")
        
        return issues
    
    async def validate_input(self, task: AgentTask) -> bool:
        """Validate task input.
        
        Args:
            task: Task to validate
            
        Returns:
            True if valid
        """
        # Must have code
        if "code" not in task.payload:
            return False
        
        return True
    
    def get_system_prompt(self) -> str:
        """Get system prompt for critic.
        
        Returns:
            System prompt
        """
        return """You are the Critic Agent for Aegis-CLI.

Your role is to review code for:

1. **Security**:
   - No eval() or exec()
   - No hardcoded secrets
   - SQL injection prevention
   - Input validation

2. **Type Safety**:
   - All functions have type hints
   - Return types specified
   - Use Python 3.11+ syntax (| for unions)

3. **Code Quality**:
   - PEP8 compliance
   - Proper error handling
   - No bare except clauses
   - Appropriate logging

4. **Documentation**:
   - All public functions have docstrings
   - Google style docstrings
   - Clear parameter descriptions

Return FAIL status with specific issues if problems found.
Return SUCCESS only if code meets all standards.
"""
    
    def get_required_tools(self) -> list[str]:
        """Get required tools.
        
        Returns:
            List of tool names
        """
        return ["filesystem"]
