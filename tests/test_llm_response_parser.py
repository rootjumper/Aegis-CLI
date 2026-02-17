"""Tests for universal LLM response parser.

Tests parsing of responses from all providers:
- Anthropic (Claude)
- Google (Gemini)
- OpenAI (GPT-4, etc.)
- Thinking models (O1, Qwen-Thinking)
"""

import pytest
from aegis.core.llm_response_parser import LLMResponseParser, ParsingError


class MockPart:
    """Mock part for testing."""
    
    def __init__(self, content: str):
        self.content = content


class MockMessage:
    """Mock message for testing."""
    
    def __init__(self, parts: list[MockPart]):
        self.parts = parts


class MockAgentRunResult:
    """Mock AgentRunResult for testing."""
    
    def __init__(self, content: str):
        self._messages = [MockMessage([MockPart(content)])]
    
    def all_messages(self):
        return self._messages


class TestLLMResponseParser:
    """Test suite for LLMResponseParser."""
    
    def test_parser_initialization(self):
        """Test parser can be initialized."""
        parser = LLMResponseParser()
        assert parser.strict is False
        
        strict_parser = LLMResponseParser(strict=True)
        assert strict_parser.strict is True
    
    def test_extract_raw_content(self):
        """Test raw content extraction from PydanticAI result."""
        parser = LLMResponseParser()
        
        # Test with content
        result = MockAgentRunResult("def hello(): pass")
        raw = parser._extract_raw_content(result)
        assert raw == "def hello(): pass"
    
    def test_extract_raw_content_no_messages(self):
        """Test extraction fails gracefully with no messages."""
        parser = LLMResponseParser()
        
        # Mock result with no messages
        class EmptyResult:
            def all_messages(self):
                return []
        
        with pytest.raises(ValueError, match="No messages in result"):
            parser._extract_raw_content(EmptyResult())
    
    def test_remove_thinking_tags(self):
        """Test removal of thinking/reasoning tags."""
        parser = LLMResponseParser()
        
        # Single tag
        content = "<think>Some reasoning here</think>\ndef hello(): pass"
        cleaned = parser._remove_thinking_tags(content)
        assert "<think>" not in cleaned
        assert "def hello(): pass" in cleaned
        
        # Multiple tags
        content = "<think>First thought</think>\n<reasoning>More reasoning</reasoning>\ndef hello(): pass"
        cleaned = parser._remove_thinking_tags(content)
        assert "<think>" not in cleaned
        assert "<reasoning>" not in cleaned
        assert "def hello(): pass" in cleaned
        
        # Case insensitive
        content = "<THINK>Upper case</THINK>\ndef hello(): pass"
        cleaned = parser._remove_thinking_tags(content)
        assert "<THINK>" not in cleaned
        assert "def hello(): pass" in cleaned
    
    def test_extract_markdown_blocks(self):
        """Test extraction of markdown code blocks."""
        parser = LLMResponseParser()
        
        # Single Python block
        content = "Here is the code:\n```python\ndef hello(): pass\n```\nThis works."
        blocks = parser._extract_markdown_blocks(content, language='python')
        assert len(blocks) == 1
        assert blocks[0] == "def hello(): pass"
        
        # Multiple blocks
        content = "```python\ndef first(): pass\n```\n```python\ndef second(): pass\n```"
        blocks = parser._extract_markdown_blocks(content, language='python')
        assert len(blocks) == 2
        assert "def first(): pass" in blocks
        assert "def second(): pass" in blocks
        
        # No language specified (generic)
        content = "```\ndef generic(): pass\n```"
        blocks = parser._extract_markdown_blocks(content)
        assert len(blocks) == 1
        assert "def generic(): pass" in blocks
    
    def test_select_best_code_block(self):
        """Test selection of best code block from multiple options."""
        parser = LLMResponseParser()
        
        # Single block - returns it
        blocks = ["def hello(): pass"]
        best = parser._select_best_code_block(blocks)
        assert best == "def hello(): pass"
        
        # Multiple blocks - prefer function definitions
        blocks = [
            "# Just a comment",
            "def main():\n    pass",
            "x = 1"
        ]
        best = parser._select_best_code_block(blocks)
        assert "def main()" in best
        
        # Penalize example blocks
        blocks = [
            'def main():\n    """Main function."""\n    pass',
            'if __name__ == "__main__":\n    main()'
        ]
        best = parser._select_best_code_block(blocks)
        assert "def main()" in best
        assert "if __name__" not in best
    
    def test_clean_raw_code(self):
        """Test cleaning of raw code without markdown."""
        parser = LLMResponseParser()
        
        # Plain code - no cleaning needed
        content = "def hello(): pass"
        cleaned = parser._clean_raw_code(content)
        assert cleaned == "def hello(): pass"
        
        # Code with explanation before
        content = "Here is a function:\ndef hello(): pass"
        cleaned = parser._clean_raw_code(content)
        assert "Here is" not in cleaned
        assert "def hello(): pass" in cleaned
        
        # Code with comments and imports
        content = "import os\n\ndef hello():\n    pass"
        cleaned = parser._clean_raw_code(content)
        assert "import os" in cleaned
        assert "def hello():" in cleaned
    
    def test_extract_text(self):
        """Test extraction of plain text."""
        parser = LLMResponseParser()
        
        # Text with thinking tags
        content = "<think>Reasoning</think>\nThis is the answer."
        text = parser._extract_text(content)
        assert "<think>" not in text
        assert "This is the answer." in text
        
        # Text with code blocks
        content = "Here is text.\n```python\ncode\n```\nMore text."
        text = parser._extract_text(content)
        assert "code" not in text
        assert "Here is text." in text
        assert "More text." in text
    
    def test_validate_code(self):
        """Test Python code validation."""
        parser = LLMResponseParser()
        
        # Valid code
        valid, error = parser.validate_code("def hello(): pass")
        assert valid is True
        assert error == ""
        
        # Invalid syntax
        valid, error = parser.validate_code("def hello( pass")
        assert valid is False
        assert "Syntax error" in error
        
        # Valid complex code
        code = '''
def hello_world() -> None:
    """Print greeting."""
    print("Hello, World!")
'''
        valid, error = parser.validate_code(code)
        assert valid is True
        assert error == ""


class TestProviderFormats:
    """Test parsing of different provider response formats."""
    
    def test_anthropic_claude_plain(self):
        """Test Anthropic Claude response (plain code)."""
        parser = LLMResponseParser()
        
        # Claude returns clean code
        result = MockAgentRunResult('def hello_world() -> None:\n    """Print greeting."""\n    print("Hello, World!")')
        code = parser.parse(result, content_type='code')
        
        assert 'def hello_world()' in code
        assert 'print("Hello, World!")' in code
        
        # Should be valid Python
        is_valid, _ = parser.validate_code(code)
        assert is_valid
    
    def test_anthropic_claude_markdown(self):
        """Test Anthropic Claude response (with markdown)."""
        parser = LLMResponseParser()
        
        # Claude may also use markdown
        result = MockAgentRunResult(
            '```python\ndef hello_world() -> None:\n    """Print greeting."""\n    print("Hello, World!")\n```'
        )
        code = parser.parse(result, content_type='code')
        
        assert 'def hello_world()' in code
        assert 'print("Hello, World!")' in code
        assert '```' not in code  # Markdown should be removed
        
        # Should be valid Python
        is_valid, _ = parser.validate_code(code)
        assert is_valid
    
    def test_google_gemini_format(self):
        """Test Google Gemini response (always markdown with explanations)."""
        parser = LLMResponseParser()
        
        # Gemini always wraps in markdown with explanations
        content = """Here's a hello world function:

```python
def hello_world() -> None:
    \"\"\"Print greeting.\"\"\"
    print("Hello, World!")
```

This function demonstrates basic Python syntax."""
        
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert 'def hello_world()' in code
        assert 'print("Hello, World!")' in code
        assert "Here's a" not in code  # Explanation should be removed
        assert "This function" not in code  # Explanation should be removed
        assert '```' not in code  # Markdown should be removed
        
        # Should be valid Python
        is_valid, _ = parser.validate_code(code)
        assert is_valid
    
    def test_openai_format(self):
        """Test OpenAI response format."""
        parser = LLMResponseParser()
        
        # OpenAI can be plain or markdown
        result = MockAgentRunResult('def hello_world() -> None:\n    print("Hello, World!")')
        code = parser.parse(result, content_type='code')
        
        assert 'def hello_world()' in code
        assert 'print("Hello, World!")' in code
        
        is_valid, _ = parser.validate_code(code)
        assert is_valid
    
    def test_thinking_model_format(self):
        """Test thinking model format (O1, Qwen-Thinking)."""
        parser = LLMResponseParser()
        
        # Thinking models include reasoning in tags
        content = """<think>
Okay, the user wants a hello world function.
I need to create a simple function that prints a greeting.
Let me write it with proper type hints and docstring.
</think>

```python
def hello_world() -> None:
    \"\"\"Print greeting.\"\"\"
    print("Hello, World!")
```"""
        
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert 'def hello_world()' in code
        assert 'print("Hello, World!")' in code
        assert '<think>' not in code  # Thinking tags should be removed
        assert 'Okay, the user' not in code  # Reasoning should be removed
        assert '```' not in code  # Markdown should be removed
        
        # Should be valid Python
        is_valid, _ = parser.validate_code(code)
        assert is_valid
    
    def test_multiple_code_blocks_selects_best(self):
        """Test that parser selects the best block from multiple."""
        parser = LLMResponseParser()
        
        # Gemini sometimes provides examples
        content = """Here's the function:

```python
def hello_world() -> None:
    \"\"\"Print greeting.\"\"\"
    print("Hello, World!")
```

And here's how to use it:

```python
if __name__ == "__main__":
    hello_world()
```"""
        
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        # Should select the main function, not the example
        assert 'def hello_world()' in code
        assert 'if __name__' not in code  # Example should not be selected
        
        is_valid, _ = parser.validate_code(code)
        assert is_valid


class TestStrictMode:
    """Test strict mode behavior."""
    
    def test_strict_mode_raises_on_empty(self):
        """Test that strict mode raises errors."""
        parser = LLMResponseParser(strict=True)
        
        # Empty result should raise
        class EmptyResult:
            def all_messages(self):
                return []
        
        with pytest.raises(ParsingError) as exc_info:
            parser.parse(EmptyResult(), content_type='code')
        
        assert exc_info.value.stage == "extraction"
    
    def test_non_strict_returns_empty(self):
        """Test that non-strict mode returns empty string on failure."""
        parser = LLMResponseParser(strict=False)
        
        # Empty result should return empty string
        class EmptyResult:
            def all_messages(self):
                return []
        
        result = parser.parse(EmptyResult(), content_type='code')
        assert result == ""


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_code_with_triple_quotes(self):
        """Test code containing triple quotes."""
        parser = LLMResponseParser()
        
        code_with_docstring = '''def hello() -> None:
    """This is a docstring with triple quotes."""
    print("Hello")'''
        
        result = MockAgentRunResult(code_with_docstring)
        code = parser.parse(result, content_type='code')
        
        assert '"""This is a docstring' in code
        is_valid, _ = parser.validate_code(code)
        assert is_valid
    
    def test_code_with_markdown_inside_string(self):
        """Test code containing markdown-like strings."""
        parser = LLMResponseParser()
        
        code = 'def test():\n    x = "```python code```"\n    return x'
        result = MockAgentRunResult(code)
        extracted = parser.parse(result, content_type='code')
        
        assert 'def test()' in extracted
        is_valid, _ = parser.validate_code(extracted)
        assert is_valid
    
    def test_empty_code_blocks(self):
        """Test handling of empty code blocks."""
        parser = LLMResponseParser()
        
        content = "```python\n\n```\nNo code here."
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        # Should fall back to raw content
        assert code is not None
    
    def test_multiline_function(self):
        """Test complex multiline function."""
        parser = LLMResponseParser()
        
        complex_code = '''def calculate_fibonacci(n: int) -> int:
    """Calculate nth Fibonacci number.
    
    Args:
        n: The position in the Fibonacci sequence
        
    Returns:
        The nth Fibonacci number
    """
    if n <= 1:
        return n
    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)'''
        
        result = MockAgentRunResult(f"```python\n{complex_code}\n```")
        code = parser.parse(result, content_type='code')
        
        assert 'def calculate_fibonacci' in code
        assert 'Args:' in code
        assert 'Returns:' in code
        
        is_valid, _ = parser.validate_code(code)
        assert is_valid
