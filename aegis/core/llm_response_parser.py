"""
Universal LLM response parser.

Works with all providers:
- Anthropic (Claude)
- Google (Gemini)
- OpenAI (GPT-4, etc.)
- Ollama (all models)
- LM Studio (all models)
- Thinking models (O1, Qwen-Thinking)

Architecture:
1. Provider-agnostic extraction (PydanticAI handles provider differences)
2. Tool call extraction (for Llama 3.1, GPT-4 with tools)
3. Format detection and normalization (markdown, thinking tags, etc.)
4. Syntax validation and feedback
"""

import re
import ast
import json
from typing import Literal, Any


class ParsingError(Exception):
    """Raised when response parsing fails."""
    
    def __init__(self, message: str, raw_content: str, stage: str):
        """Initialize parsing error.
        
        Args:
            message: Error message
            raw_content: The raw content that failed to parse
            stage: Stage where parsing failed (e.g., 'extraction', 'validation')
        """
        super().__init__(message)
        self.raw_content = raw_content
        self.stage = stage


class LLMResponseParser:
    """Universal parser for any LLM response format."""
    
    # Thinking/reasoning tag patterns (extended for multi-language support)
    THINKING_TAGS = [
        'think', 'thinking', 'reasoning', 'thought', 
        'analysis', 'rationale', 'chain-of-thought',
        '反思', '思考', '分析'  # Chinese thinking tags
    ]
    
    # Code fence patterns
    CODE_FENCE_PYTHON = r'```(?:python|py)?\s*\n(.*?)\n```'
    CODE_FENCE_ANY = r'```\w*\s*\n(.*?)\n```'
    
    # Tool names that indicate code generation
    CODE_TOOL_NAMES = [
        'python', 'execute_python', 'run_code', 'run_python',
        'code_execution', 'python_code', 'execute_code',
        'run_script', 'python_script', 'code_interpreter',
        'ipython', 'python_repl', 'code_tool'
    ]
    
    # Parameter names that may contain code in tool arguments
    CODE_PARAM_NAMES = [
        'code', 'python_code', 'script', 'source',
        'program', 'source_code', 'python_script',
        'content', 'body', 'implementation'
    ]
    
    # Refusal patterns
    REFUSAL_PATTERNS = [
        r"i cannot",
        r"i'm not able",
        r"i can't",
        r"ethical guidelines",
        r"not appropriate",
        r"against my programming",
        r"safety guidelines"
    ]
    
    def __init__(self, strict: bool = False, log_failures: bool = False):
        """
        Initialize parser.
        
        Args:
            strict: If True, raise errors on parsing failures.
                   If False, return best-effort extraction.
            log_failures: If True, log parsing failures for debugging.
        """
        self.strict = strict
        self.log_failures = log_failures
        self._stats = {
            'total_parsed': 0,
            'tool_call_extractions': 0,
            'markdown_extractions': 0,
            'plain_extractions': 0,
            'failures': 0
        }
    
    def parse(
        self, 
        result: Any, 
        content_type: Literal['code', 'text', 'structured'] = 'code'
    ) -> str:
        """
        Universal parsing entry point.
        
        Args:
            result: PydanticAI AgentRunResult (any provider)
            content_type: Expected content type
                - 'code': Extract Python code
                - 'text': Extract plain text
                - 'structured': Extract structured data
        
        Returns:
            Parsed content string
            
        Raises:
            ParsingError: If strict=True and parsing fails
        """
        self._stats['total_parsed'] += 1
        
        # Tier 1: Check tool calls FIRST (critical for Llama 3.1, GPT-4 with tools)
        try:
            messages = result.all_messages()
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                    code = self._extract_from_tool_calls(last_message.tool_calls)
                    if code:
                        self._stats['tool_call_extractions'] += 1
                        return code
        except Exception:
            pass  # Fall through to content extraction
        
        # Tier 2: Extract raw content (provider-agnostic)
        try:
            raw_content = self._extract_raw_content(result)
        except Exception as e:
            self._stats['failures'] += 1
            if self.strict:
                raise ParsingError(f"Failed to extract content: {e}", "", "extraction")
            return ""
        
        # Tier 3: Check for refusals
        if self._is_refusal(raw_content):
            self._stats['failures'] += 1
            if self.strict:
                raise ParsingError("LLM refused to generate content", raw_content, "refusal")
            return ""
        
        # Tier 4: Format-specific processing
        if content_type == 'code':
            result_code = self._extract_code(raw_content)
            if result_code:
                return result_code
            self._stats['failures'] += 1
            return ""
        elif content_type == 'text':
            return self._extract_text(raw_content)
        else:
            return raw_content
    
    def _extract_raw_content(self, result: Any) -> str:
        """
        Extract raw content from PydanticAI result.
        
        This works for ALL providers because PydanticAI normalizes them.
        
        Args:
            result: PydanticAI AgentRunResult
            
        Returns:
            Raw text content from the LLM response
            
        Raises:
            ValueError: If content cannot be extracted
        """
        messages = result.all_messages()
        
        if not messages:
            raise ValueError("No messages in result")
        
        last_message = messages[-1]
        
        # PydanticAI normalizes all providers to have .parts
        if not hasattr(last_message, 'parts') or not last_message.parts:
            raise ValueError(f"No content parts in message: {type(last_message)}")
        
        # Get content from first part
        first_part = last_message.parts[0]
        
        # Handle different part types
        if hasattr(first_part, 'content'):
            return str(first_part.content)
        elif hasattr(first_part, 'text'):
            return str(first_part.text)
        else:
            return str(first_part)
    
    def _extract_from_tool_calls(self, tool_calls: list) -> str:
        """
        Extract code from tool calls (critical for Llama 3.1, GPT-4 with tools).
        
        Args:
            tool_calls: List of tool call objects
            
        Returns:
            Extracted code or empty string if no code found
        """
        for tool_call in tool_calls:
            # Check if this is a code-generating tool
            tool_name = ''
            if hasattr(tool_call, 'function') and hasattr(tool_call.function, 'name'):
                tool_name = tool_call.function.name.lower()
            elif hasattr(tool_call, 'name'):
                tool_name = tool_call.name.lower()
            
            # Skip non-code tools
            if not any(code_tool in tool_name for code_tool in self.CODE_TOOL_NAMES):
                continue
            
            # Extract arguments
            args = None
            if hasattr(tool_call, 'function') and hasattr(tool_call.function, 'arguments'):
                args = tool_call.function.arguments
            elif hasattr(tool_call, 'arguments'):
                args = tool_call.arguments
            
            if not args:
                continue
            
            # Handle dict args (Pattern 5)
            if isinstance(args, dict):
                code = self._extract_code_from_dict(args)
                if code:
                    return code
            
            # Handle JSON string args (Pattern 6)
            elif isinstance(args, str):
                code = self._extract_code_from_json_string(args)
                if code:
                    return code
        
        return ""
    
    def _extract_code_from_dict(self, args: dict) -> str:
        """Extract code from dictionary arguments."""
        for param_name in self.CODE_PARAM_NAMES:
            if param_name in args:
                code = args[param_name]
                if isinstance(code, str) and code.strip():
                    return code.strip()
        return ""
    
    def _extract_code_from_json_string(self, json_str: str) -> str:
        """
        Extract code from JSON string arguments with repair strategies.
        
        Handles malformed JSON (Pattern 7/8) from Llama variants.
        """
        # Strategy 1: Try direct JSON parsing
        try:
            args = json.loads(json_str)
            if isinstance(args, dict):
                return self._extract_code_from_dict(args)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Repair common JSON issues
        repaired = self._repair_json(json_str)
        if repaired != json_str:
            try:
                args = json.loads(repaired)
                if isinstance(args, dict):
                    return self._extract_code_from_dict(args)
            except json.JSONDecodeError:
                pass
        
        # Strategy 3: Regex extraction as last resort
        for param_name in self.CODE_PARAM_NAMES:
            pattern = rf'"{param_name}"\s*:\s*"((?:[^"\\]|\\.)*)"'
            match = re.search(pattern, json_str, re.DOTALL)
            if match:
                code = match.group(1)
                # Unescape the code
                code = code.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
                if code.strip():
                    return code.strip()
        
        return ""
    
    def _repair_json(self, json_str: str) -> str:
        """
        Repair common JSON malformations from LLMs.
        
        Handles:
        - Unescaped quotes in strings
        - Missing closing brackets
        - Trailing garbage
        """
        # Fix 1: Escape unescaped quotes (simplified approach)
        # This is tricky - we'll try to fix the most common case
        repaired = json_str
        
        # Fix 2: Remove trailing garbage after last }
        last_brace = repaired.rfind('}')
        if last_brace > 0:
            repaired = repaired[:last_brace + 1]
        
        # Fix 3: Add missing closing bracket if needed
        open_braces = repaired.count('{')
        close_braces = repaired.count('}')
        if open_braces > close_braces:
            repaired += '}' * (open_braces - close_braces)
        
        return repaired
    
    def _is_refusal(self, content: str) -> bool:
        """
        Detect if the LLM refused to generate content.
        
        Args:
            content: Content to check
            
        Returns:
            True if content appears to be a refusal
        """
        content_lower = content.lower()
        return any(re.search(pattern, content_lower) for pattern in self.REFUSAL_PATTERNS)
    
    def _extract_code(self, raw_content: str) -> str:
        """
        Extract Python code from any format.
        
        Handles:
        - Claude: Plain code or markdown
        - Gemini: Always markdown with explanations
        - OpenAI: Plain or markdown
        - Thinking models: <think> tags + markdown
        
        Args:
            raw_content: Raw text from LLM
            
        Returns:
            Extracted Python code
        """
        # Phase 1: Remove thinking tags (for thinking models)
        cleaned = self._remove_thinking_tags(raw_content)
        
        # Phase 2: Extract from markdown blocks (for Gemini, some others)
        code_blocks = self._extract_markdown_blocks(cleaned, language='python')
        
        if code_blocks:
            # Phase 3: Select best block (if multiple)
            self._stats['markdown_extractions'] += 1
            code = self._select_best_code_block(code_blocks)
            
            # Check for truncation
            if self._is_truncated(code):
                if self.log_failures:
                    import logging
                    logging.warning(f"Code appears truncated: {code[:100]}...")
            
            return code
        
        # Phase 4: No markdown - clean up raw text (for Claude, simple responses)
        self._stats['plain_extractions'] += 1
        code = self._clean_raw_code(cleaned)
        
        # Check for truncation
        if code and self._is_truncated(code):
            if self.log_failures:
                import logging
                logging.warning(f"Code appears truncated: {code[:100]}...")
        
        return code
    
    def _is_truncated(self, code: str) -> bool:
        """
        Detect if code appears to be truncated.
        
        Args:
            code: Code to check
            
        Returns:
            True if code appears truncated
        """
        if not code:
            return False
        
        # Check for unbalanced quotes
        single_quotes = code.count("'") - code.count("\\'")
        double_quotes = code.count('"') - code.count('\\"')
        if single_quotes % 2 != 0 or double_quotes % 2 != 0:
            return True
        
        # Check for unbalanced brackets/parens
        if code.count('(') != code.count(')'):
            return True
        if code.count('[') != code.count(']'):
            return True
        if code.count('{') != code.count('}'):
            return True
        
        return False
    
    def _remove_thinking_tags(self, content: str) -> str:
        """Remove all thinking/reasoning tag patterns.
        
        Args:
            content: Content that may contain thinking tags
            
        Returns:
            Content with thinking tags removed
        """
        for tag in self.THINKING_TAGS:
            # Escape tag to prevent regex injection
            escaped_tag = re.escape(tag)
            pattern = f'<{escaped_tag}>.*?</{escaped_tag}>'
            content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
        return content.strip()
    
    def _extract_markdown_blocks(self, content: str, language: str | None = None) -> list[str]:
        """Extract code blocks from markdown fences.
        
        Args:
            content: Content that may contain markdown code blocks
            language: Optional language filter (e.g., 'python')
            
        Returns:
            List of extracted code blocks
        """
        if language:
            pattern = rf'```(?:{language})?\s*\n(.*?)\n```'
        else:
            pattern = self.CODE_FENCE_ANY
        
        blocks = re.findall(pattern, content, re.DOTALL)
        return [block.strip() for block in blocks if block.strip()]
    
    def _select_best_code_block(self, blocks: list[str]) -> str:
        """Select primary code block from multiple options.
        
        Uses heuristics to choose the most relevant code block:
        - Prefers blocks with function/class definitions
        - Penalizes example/runner blocks
        - Favors larger blocks
        - Prefers blocks with docstrings
        
        Args:
            blocks: List of code blocks
            
        Returns:
            The best code block
        """
        if len(blocks) == 1:
            return blocks[0]
        
        # Score each block
        def score_block(code: str) -> int:
            score = 0
            
            # Prefer blocks with function/class definitions
            if 'def ' in code:
                score += 20
            if 'class ' in code:
                score += 20
            
            # Penalize example/runner blocks
            if 'if __name__' in code:
                score -= 10
            if '# Example' in code or '# Usage' in code:
                score -= 5
            
            # Prefer larger blocks (main implementation)
            score += min(len(code) // 10, 50)  # Cap size bonus
            
            # Prefer blocks with docstrings
            if '"""' in code or "'''" in code:
                score += 10
            
            return score
        
        return max(blocks, key=score_block)
    
    def _clean_raw_code(self, content: str) -> str:
        """Clean up raw code (no markdown wrapping).
        
        Removes common explanatory text and returns just the code.
        
        Args:
            content: Raw content that may contain code and explanations
            
        Returns:
            Cleaned code
        """
        lines = content.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip common explanatory prefixes
            if any(stripped.startswith(prefix) for prefix in [
                'Here', 'This', 'The function', 'The code', 
                'Note:', 'Example:', 'Usage:'
            ]):
                if not in_code:  # Only skip before code starts
                    continue
            
            # Detect code start
            if any(keyword in line for keyword in ['def ', 'class ', 'import ', 'from ']):
                in_code = True
            
            if in_code or stripped.startswith(('#', '"""', "'''")):
                code_lines.append(line)
        
        result = '\n'.join(code_lines).strip()
        
        # If nothing extracted, return original cleaned content
        return result if result else content.strip()
    
    def _extract_text(self, raw_content: str) -> str:
        """Extract plain text (remove markdown and tags).
        
        Args:
            raw_content: Raw content that may contain markdown/tags
            
        Returns:
            Plain text content
        """
        # Remove thinking tags
        cleaned = self._remove_thinking_tags(raw_content)
        
        # Remove code blocks
        cleaned = re.sub(self.CODE_FENCE_ANY, '', cleaned, flags=re.DOTALL)
        
        return cleaned.strip()
    
    def validate_code(self, code: str) -> tuple[bool, str]:
        """
        Validate Python code syntax.
        
        Args:
            code: Python code to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def get_stats(self) -> dict:
        """
        Get parsing statistics.
        
        Returns:
            Dictionary with parsing statistics
        """
        total = self._stats['total_parsed']
        if total == 0:
            success_rate = 0.0
        else:
            success_rate = (total - self._stats['failures']) / total
        
        return {
            **self._stats,
            'success_rate': success_rate
        }
