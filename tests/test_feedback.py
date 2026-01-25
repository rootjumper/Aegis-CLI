"""Tests for feedback parser."""

import pytest
from aegis.core.feedback import FeedbackParser, Feedback


def test_parse_pytest_output() -> None:
    """Test parsing pytest output."""
    output = """
    test_example.py::test_function FAILED
    AssertionError: Expected 5, got 3
    test_example.py:10: error
    """
    
    feedbacks = FeedbackParser.parse_pytest_output(output)
    
    assert len(feedbacks) > 0
    assert any(f.severity == "ERROR" for f in feedbacks)


def test_parse_pylint_output() -> None:
    """Test parsing pylint output."""
    output = """
    example.py:15:0: C0111: Missing module docstring
    example.py:20:4: E0001: Syntax error
    """
    
    feedbacks = FeedbackParser.parse_pylint_output(output)
    
    assert len(feedbacks) == 2
    assert feedbacks[0].file_path == "example.py"
    assert feedbacks[1].severity == "ERROR"


def test_parse_mypy_output() -> None:
    """Test parsing mypy output."""
    output = """
    example.py:10: error: Missing return statement
    example.py:15: warning: Unused variable 'x'
    """
    
    feedbacks = FeedbackParser.parse_mypy_output(output)
    
    assert len(feedbacks) == 2
    assert feedbacks[0].severity == "ERROR"
    assert feedbacks[1].severity == "WARNING"


def test_format_for_agent() -> None:
    """Test formatting feedback for agent consumption."""
    feedbacks = [
        Feedback(
            severity="ERROR",
            file_path="test.py",
            line_number=10,
            message="Test error"
        ),
        Feedback(
            severity="WARNING",
            message="Test warning"
        )
    ]
    
    formatted = FeedbackParser.format_for_agent(feedbacks)
    
    assert "## Feedback Summary" in formatted
    assert "### Errors" in formatted
    assert "test.py:10" in formatted
