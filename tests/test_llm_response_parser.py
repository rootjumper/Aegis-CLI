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


class TestToolCallExtraction:
    """Test tool call extraction patterns (P0 - Critical for Llama 3.1)."""
    
    def test_tool_call_dict_args(self):
        """Test Pattern 5: Tool call with dict arguments."""
        parser = LLMResponseParser()
        
        # Mock tool call with dict args
        class MockToolCall:
            def __init__(self, name, args):
                self.function = type('Function', (), {'name': name, 'arguments': args})()
        
        class MockMessageWithTools:
            def __init__(self, tool_calls):
                self.tool_calls = tool_calls
                self.parts = [MockPart("Some conversational text")]
        
        class MockResultWithTools:
            def __init__(self, tool_calls):
                self._messages = [MockMessageWithTools(tool_calls)]
            def all_messages(self):
                return self._messages
        
        # Test with 'code' parameter
        tool_calls = [MockToolCall('python', {'code': 'def hello(): pass'})]
        result = MockResultWithTools(tool_calls)
        code = parser.parse(result, content_type='code')
        
        assert code == 'def hello(): pass'
        assert parser._stats['tool_call_extractions'] == 1
    
    def test_tool_call_multiple_params(self):
        """Test tool calls with different parameter names."""
        parser = LLMResponseParser()
        
        class MockToolCall:
            def __init__(self, name, args):
                self.function = type('Function', (), {'name': name, 'arguments': args})()
        
        class MockMessageWithTools:
            def __init__(self, tool_calls):
                self.tool_calls = tool_calls
                self.parts = [MockPart("Text")]
        
        class MockResultWithTools:
            def __init__(self, tool_calls):
                self._messages = [MockMessageWithTools(tool_calls)]
            def all_messages(self):
                return self._messages
        
        # Test with 'python_code' parameter
        tool_calls = [MockToolCall('execute_python', {'python_code': 'x = 1'})]
        result = MockResultWithTools(tool_calls)
        code = parser.parse(result, content_type='code')
        assert code == 'x = 1'
        
        # Test with 'script' parameter
        parser2 = LLMResponseParser()
        tool_calls2 = [MockToolCall('run_code', {'script': 'y = 2'})]
        result2 = MockResultWithTools(tool_calls2)
        code2 = parser2.parse(result2, content_type='code')
        assert code2 == 'y = 2'
    
    def test_tool_call_json_string_args(self):
        """Test Pattern 6: Tool call with JSON string arguments."""
        parser = LLMResponseParser()
        
        class MockToolCall:
            def __init__(self, name, args):
                self.function = type('Function', (), {'name': name, 'arguments': args})()
        
        class MockMessageWithTools:
            def __init__(self, tool_calls):
                self.tool_calls = tool_calls
                self.parts = [MockPart("Text")]
        
        class MockResultWithTools:
            def __init__(self, tool_calls):
                self._messages = [MockMessageWithTools(tool_calls)]
            def all_messages(self):
                return self._messages
        
        # JSON string with escaped newlines
        json_args = '{"code":"def hello():\\n    pass"}'
        tool_calls = [MockToolCall('python', json_args)]
        result = MockResultWithTools(tool_calls)
        code = parser.parse(result, content_type='code')
        
        assert 'def hello():' in code
        assert 'pass' in code
    
    def test_malformed_json_repair(self):
        """Test Pattern 7/8: Malformed JSON repair from Llama variants."""
        parser = LLMResponseParser()
        
        # Test unescaped quotes repair
        malformed = '{"code":"def foo():\\n    return True"}'
        repaired = parser._repair_json(malformed)
        # Should at least not crash
        assert isinstance(repaired, str)
        
        # Test missing closing bracket
        malformed2 = '{"code":"def bar(): pass"'
        repaired2 = parser._repair_json(malformed2)
        assert repaired2.count('{') == repaired2.count('}')
    
    def test_tool_call_filters_non_code_tools(self):
        """Test that only code-generating tools are processed."""
        parser = LLMResponseParser()
        
        class MockToolCall:
            def __init__(self, name, args):
                self.function = type('Function', (), {'name': name, 'arguments': args})()
        
        class MockMessageWithTools:
            def __init__(self, tool_calls):
                self.tool_calls = tool_calls
                self.parts = [MockPart("def fallback(): pass")]
        
        class MockResultWithTools:
            def __init__(self, tool_calls):
                self._messages = [MockMessageWithTools(tool_calls)]
            def all_messages(self):
                return self._messages
        
        # Non-code tool should be ignored, fall back to content
        tool_calls = [MockToolCall('search_web', {'query': 'python'})]
        result = MockResultWithTools(tool_calls)
        code = parser.parse(result, content_type='code')
        
        # Should extract from content, not tool call
        assert 'def fallback(): pass' in code
        assert parser._stats['tool_call_extractions'] == 0


class TestRefusalDetection:
    """Test refusal detection (Pattern 14)."""
    
    def test_detects_ethical_refusal(self):
        """Test detection of ethical guideline refusals."""
        parser = LLMResponseParser(strict=True)
        
        refusal = "I cannot generate that code as it violates ethical guidelines."
        result = MockAgentRunResult(refusal)
        
        with pytest.raises(ParsingError) as exc_info:
            parser.parse(result, content_type='code')
        
        assert exc_info.value.stage == "refusal"
    
    def test_detects_capability_refusal(self):
        """Test detection of capability refusals."""
        parser = LLMResponseParser(strict=True)
        
        refusal = "I'm not able to write code that could be harmful."
        result = MockAgentRunResult(refusal)
        
        with pytest.raises(ParsingError):
            parser.parse(result, content_type='code')
    
    def test_non_strict_returns_empty_on_refusal(self):
        """Test non-strict mode returns empty on refusal."""
        parser = LLMResponseParser(strict=False)
        
        refusal = "I cannot help with that request."
        result = MockAgentRunResult(refusal)
        code = parser.parse(result, content_type='code')
        
        assert code == ""


class TestTruncationDetection:
    """Test truncation detection (Pattern 13)."""
    
    def test_detects_unbalanced_quotes(self):
        """Test detection of unbalanced quotes."""
        parser = LLMResponseParser()
        
        truncated = 'def foo():\n    msg = "Hello'
        assert parser._is_truncated(truncated) is True
        
        complete = 'def foo():\n    msg = "Hello"'
        assert parser._is_truncated(complete) is False
    
    def test_detects_unbalanced_parens(self):
        """Test detection of unbalanced parentheses."""
        parser = LLMResponseParser()
        
        truncated = 'def foo():\n    print("test"'
        assert parser._is_truncated(truncated) is True
        
        complete = 'def foo():\n    print("test")'
        assert parser._is_truncated(complete) is False
    
    def test_detects_unbalanced_brackets(self):
        """Test detection of unbalanced brackets."""
        parser = LLMResponseParser()
        
        truncated = 'def foo():\n    x = [1, 2, 3'
        assert parser._is_truncated(truncated) is True
        
        complete = 'def foo():\n    x = [1, 2, 3]'
        assert parser._is_truncated(complete) is False


class TestStatistics:
    """Test statistics tracking."""
    
    def test_stats_initialization(self):
        """Test stats are initialized correctly."""
        parser = LLMResponseParser()
        stats = parser.get_stats()
        
        assert stats['total_parsed'] == 0
        assert stats['tool_call_extractions'] == 0
        assert stats['markdown_extractions'] == 0
        assert stats['plain_extractions'] == 0
        assert stats['failures'] == 0
        assert stats['success_rate'] == 0.0
    
    def test_stats_tracking(self):
        """Test stats are tracked correctly."""
        parser = LLMResponseParser()
        
        # Parse markdown
        result1 = MockAgentRunResult('```python\ndef test(): pass\n```')
        parser.parse(result1, content_type='code')
        
        stats = parser.get_stats()
        assert stats['total_parsed'] == 1
        assert stats['markdown_extractions'] == 1
        
        # Parse plain
        result2 = MockAgentRunResult('def test2(): pass')
        parser.parse(result2, content_type='code')
        
        stats = parser.get_stats()
        assert stats['total_parsed'] == 2
        assert stats['plain_extractions'] == 1
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        parser = LLMResponseParser()
        
        # Successful parse
        result1 = MockAgentRunResult('def test(): pass')
        parser.parse(result1, content_type='code')
        
        stats = parser.get_stats()
        assert stats['success_rate'] == 1.0
        
        # Failed parse (empty result)
        class EmptyResult:
            def all_messages(self):
                return []
        
        parser.parse(EmptyResult(), content_type='code')
        
        stats = parser.get_stats()
        assert stats['total_parsed'] == 2
        assert stats['failures'] == 1
        assert stats['success_rate'] == 0.5


class TestChineseThinkingTags:
    """Test Chinese thinking tag removal."""
    
    def test_remove_chinese_thinking_tags(self):
        """Test removal of Chinese thinking tags."""
        parser = LLMResponseParser()
        
        content = "<反思>考虑PEP8规范</反思>\ndef hello(): pass"
        cleaned = parser._remove_thinking_tags(content)
        
        assert "<反思>" not in cleaned
        assert "考虑PEP8规范" not in cleaned
        assert "def hello(): pass" in cleaned
    
    def test_mixed_language_thinking_tags(self):
        """Test removal of mixed language thinking tags."""
        parser = LLMResponseParser()
        
        content = """<think>English reasoning</think>
<思考>中文思考</思考>
def hello(): pass"""
        cleaned = parser._remove_thinking_tags(content)
        
        assert "<think>" not in cleaned
        assert "<思考>" not in cleaned
        assert "def hello(): pass" in cleaned


class TestConversationalWrapping:
    """Test conversational wrapper removal (Pattern 10)."""
    
    def test_removes_prefix_explanation(self):
        """Test removal of explanatory text before code."""
        parser = LLMResponseParser()
        
        content = "Here is the code you requested:\ndef hello(): pass"
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert "Here is" not in code
        assert "def hello(): pass" in code
    
    def test_preserves_code_comments(self):
        """Test that code comments are preserved."""
        parser = LLMResponseParser()
        
        content = """def hello():
    # This is a comment
    pass"""
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert "# This is a comment" in code


class TestLanguageTagVariants:
    """Test language tag handling (Pattern 11)."""
    
    def test_python_tag_variant(self):
        """Test 'python' tag."""
        parser = LLMResponseParser()
        
        content = "```python\ndef test(): pass\n```"
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert "def test(): pass" in code
        assert "```" not in code
    
    def test_py_tag_variant(self):
        """Test 'py' tag."""
        parser = LLMResponseParser()
        
        content = "```py\ndef test(): pass\n```"
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert "def test(): pass" in code
    
    def test_no_language_tag(self):
        """Test no language tag."""
        parser = LLMResponseParser()
        
        content = "```\ndef test(): pass\n```"
        result = MockAgentRunResult(content)
        code = parser.parse(result, content_type='code')
        
        assert "def test(): pass" in code


class TestLogFailuresOption:
    """Test log_failures option."""
    
    def test_log_failures_initialization(self):
        """Test log_failures option is stored."""
        parser = LLMResponseParser(log_failures=True)
        assert parser.log_failures is True
        
        parser2 = LLMResponseParser(log_failures=False)
        assert parser2.log_failures is False
