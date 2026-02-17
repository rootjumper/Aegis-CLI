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
2. Format detection and normalization (markdown, thinking tags, etc.)
3. Syntax validation and feedback
"""

import re
import ast
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
    
    # Thinking/reasoning tag patterns
    THINKING_TAGS = [
        'think', 'thinking', 'reasoning', 'thought', 
        'analysis', 'rationale', 'chain-of-thought'
    ]
    
    # Code fence patterns
    CODE_FENCE_PYTHON = r'```(?:python|py)?\s*\n(.*?)\n```'
    CODE_FENCE_ANY = r'```\w*\s*\n(.*?)\n```'
    
    def __init__(self, strict: bool = False):
        """
        Initialize parser.
        
        Args:
            strict: If True, raise errors on parsing failures.
                   If False, return best-effort extraction.
        """
        self.strict = strict
    
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
        # Stage 1: Extract raw content (provider-agnostic)
        try:
            raw_content = self._extract_raw_content(result)
        except Exception as e:
            if self.strict:
                raise ParsingError(f"Failed to extract content: {e}", "", "extraction")
            return ""
        
        # Stage 2: Format-specific processing
        if content_type == 'code':
            return self._extract_code(raw_content)
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
            return self._select_best_code_block(code_blocks)
        
        # Phase 4: No markdown - clean up raw text (for Claude, simple responses)
        return self._clean_raw_code(cleaned)
    
    def _remove_thinking_tags(self, content: str) -> str:
        """Remove all thinking/reasoning tag patterns.
        
        Args:
            content: Content that may contain thinking tags
            
        Returns:
            Content with thinking tags removed
        """
        for tag in self.THINKING_TAGS:
            pattern = f'<{tag}>.*?</{tag}>'
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
