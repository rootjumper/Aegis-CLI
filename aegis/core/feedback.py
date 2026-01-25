"""Feedback parser for extracting actionable insights from tool outputs.

Parses pytest, pylint, mypy outputs and agent reviews to create structured feedback.
"""

import re
from typing import Any, Literal
from pydantic import BaseModel


class Feedback(BaseModel):
    """Structured feedback from tool or agent output.
    
    Attributes:
        severity: Issue severity level
        file_path: File path where issue occurred
        line_number: Line number of the issue
        message: Detailed message
        suggested_fix: Optional suggestion for fixing
    """
    severity: Literal["ERROR", "WARNING", "INFO"]
    file_path: str | None = None
    line_number: int | None = None
    message: str
    suggested_fix: str | None = None


class FeedbackParser:
    """Parser for extracting actionable feedback from various sources."""
    
    @staticmethod
    def parse_pytest_output(output: str) -> list[Feedback]:
        """Parse pytest failure output.
        
        Args:
            output: Pytest stdout/stderr
            
        Returns:
            List of Feedback objects
        """
        feedbacks: list[Feedback] = []
        
        # Pattern for pytest failures: test_file.py::test_name FAILED
        failure_pattern = r"([\w/.]+\.py)::(\w+)\s+FAILED"
        
        for match in re.finditer(failure_pattern, output):
            file_path = match.group(1)
            test_name = match.group(2)
            
            feedbacks.append(Feedback(
                severity="ERROR",
                file_path=file_path,
                message=f"Test '{test_name}' failed in {file_path}"
            ))
        
        # Pattern for assertion errors
        assertion_pattern = r"AssertionError: (.+)"
        for match in re.finditer(assertion_pattern, output):
            feedbacks.append(Feedback(
                severity="ERROR",
                message=f"Assertion failed: {match.group(1)}"
            ))
        
        # Pattern for file:line references
        file_line_pattern = r"([\w/.]+\.py):(\d+):"
        for match in re.finditer(file_line_pattern, output):
            file_path = match.group(1)
            line_number = int(match.group(2))
            
            # Try to extract surrounding context
            context_start = max(0, match.start() - 100)
            context_end = min(len(output), match.end() + 200)
            context = output[context_start:context_end].strip()
            
            feedbacks.append(Feedback(
                severity="ERROR",
                file_path=file_path,
                line_number=line_number,
                message=f"Error at {file_path}:{line_number}"
            ))
        
        return feedbacks
    
    @staticmethod
    def parse_pylint_output(output: str) -> list[Feedback]:
        """Parse pylint output.
        
        Args:
            output: Pylint stdout
            
        Returns:
            List of Feedback objects
        """
        feedbacks: list[Feedback] = []
        
        # Pattern: file.py:line:col: C0111: Missing module docstring
        pattern = r"([\w/.]+\.py):(\d+):(\d+):\s+([CWEF]\d+):\s+(.+)"
        
        for match in re.finditer(pattern, output):
            file_path = match.group(1)
            line_number = int(match.group(2))
            code = match.group(4)
            message = match.group(5)
            
            # Determine severity
            severity_char = code[0]
            if severity_char in ["E", "F"]:
                severity = "ERROR"
            elif severity_char == "W":
                severity = "WARNING"
            else:
                severity = "INFO"
            
            feedbacks.append(Feedback(
                severity=severity,
                file_path=file_path,
                line_number=line_number,
                message=f"{code}: {message}"
            ))
        
        return feedbacks
    
    @staticmethod
    def parse_mypy_output(output: str) -> list[Feedback]:
        """Parse mypy output.
        
        Args:
            output: Mypy stdout
            
        Returns:
            List of Feedback objects
        """
        feedbacks: list[Feedback] = []
        
        # Pattern: file.py:line: error: message
        pattern = r"([\w/.]+\.py):(\d+):\s+(error|warning|note):\s+(.+)"
        
        for match in re.finditer(pattern, output):
            file_path = match.group(1)
            line_number = int(match.group(2))
            level = match.group(3)
            message = match.group(4)
            
            # Map mypy levels to our severity
            severity_map = {
                "error": "ERROR",
                "warning": "WARNING",
                "note": "INFO"
            }
            severity = severity_map.get(level, "ERROR")
            
            feedbacks.append(Feedback(
                severity=severity,
                file_path=file_path,
                line_number=line_number,
                message=message
            ))
        
        return feedbacks
    
    @staticmethod
    def parse_agent_review(review_text: str) -> list[Feedback]:
        """Parse agent review comments.
        
        Args:
            review_text: Review text from critic agent
            
        Returns:
            List of Feedback objects
        """
        feedbacks: list[Feedback] = []
        
        # Look for structured comments in format:
        # [SEVERITY] file.py:line - message
        pattern = r"\[(ERROR|WARNING|INFO)\]\s+([\w/.]+\.py):(\d+)\s+-\s+(.+)"
        
        for match in re.finditer(pattern, review_text):
            severity = match.group(1)
            file_path = match.group(2)
            line_number = int(match.group(3))
            message = match.group(4)
            
            feedbacks.append(Feedback(
                severity=severity,  # type: ignore
                file_path=file_path,
                line_number=line_number,
                message=message
            ))
        
        # Also look for general security/quality issues
        if "security" in review_text.lower() or "vulnerable" in review_text.lower():
            feedbacks.append(Feedback(
                severity="ERROR",
                message="Security issue detected in code"
            ))
        
        return feedbacks
    
    @staticmethod
    def format_for_agent(feedbacks: list[Feedback]) -> str:
        """Format feedback for agent consumption.
        
        Args:
            feedbacks: List of feedback items
            
        Returns:
            Formatted feedback string
        """
        if not feedbacks:
            return "No issues found."
        
        output = ["## Feedback Summary\n"]
        
        # Group by severity
        errors = [f for f in feedbacks if f.severity == "ERROR"]
        warnings = [f for f in feedbacks if f.severity == "WARNING"]
        info = [f for f in feedbacks if f.severity == "INFO"]
        
        if errors:
            output.append("### Errors\n")
            for feedback in errors:
                location = ""
                if feedback.file_path:
                    location = f"`{feedback.file_path}"
                    if feedback.line_number:
                        location += f":{feedback.line_number}"
                    location += "` - "
                output.append(f"- {location}{feedback.message}")
                if feedback.suggested_fix:
                    output.append(f"  - **Fix:** {feedback.suggested_fix}")
            output.append("")
        
        if warnings:
            output.append("### Warnings\n")
            for feedback in warnings:
                location = ""
                if feedback.file_path:
                    location = f"`{feedback.file_path}"
                    if feedback.line_number:
                        location += f":{feedback.line_number}"
                    location += "` - "
                output.append(f"- {location}{feedback.message}")
            output.append("")
        
        return "\n".join(output)
