"""Integration test for multi-language code generation (HTML, CSS, JavaScript).

This test verifies the fix for the file writing bug where non-Python code
was being validated with Python's AST parser, causing generation failures.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from aegis.agents.coder import CoderAgent
from aegis.agents.base import AgentTask


# Skip LLM tests if no API key is configured
skip_if_no_llm = pytest.mark.skipif(
    not any([
        os.environ.get('ANTHROPIC_API_KEY'),
        os.environ.get('GOOGLE_API_KEY'),
        os.environ.get('OLLAMA_MODEL'),
        os.environ.get('LM_STUDIO_MODEL')
    ]),
    reason="No LLM provider configured"
)


@pytest.mark.asyncio
@skip_if_no_llm
async def test_coder_generates_html():
    """Test that CoderAgent can generate HTML files."""
    coder = CoderAgent()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "index.html")
        
        task = AgentTask(
            id="test-html-1",
            type="code",
            payload={
                "description": "Create a simple HTML page with a heading",
                "file_path": file_path
            },
            context={}
        )
        
        response = await coder.process(task)
        
        # Should succeed (not fail due to Python AST validation)
        assert response.status == "SUCCESS", f"Expected SUCCESS but got {response.status}: {response.errors}"
        assert "code" in response.data
        
        # Generated code should contain HTML
        code = response.data["code"]
        assert len(code) > 0
        # HTML typically has tags
        assert "<" in code or "html" in code.lower()


@pytest.mark.asyncio
@skip_if_no_llm
async def test_coder_generates_css():
    """Test that CoderAgent can generate CSS files."""
    coder = CoderAgent()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "styles.css")
        
        task = AgentTask(
            id="test-css-1",
            type="code",
            payload={
                "description": "Create CSS styles for a button",
                "file_path": file_path
            },
            context={}
        )
        
        response = await coder.process(task)
        
        # Should succeed (not fail due to Python AST validation)
        assert response.status == "SUCCESS", f"Expected SUCCESS but got {response.status}: {response.errors}"
        assert "code" in response.data
        
        # Generated code should be present
        code = response.data["code"]
        assert len(code) > 0


@pytest.mark.asyncio
@skip_if_no_llm
async def test_coder_generates_javascript():
    """Test that CoderAgent can generate JavaScript files."""
    coder = CoderAgent()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "app.js")
        
        task = AgentTask(
            id="test-js-1",
            type="code",
            payload={
                "description": "Create a JavaScript function to add two numbers",
                "file_path": file_path
            },
            context={}
        )
        
        response = await coder.process(task)
        
        # Should succeed (not fail due to Python AST validation)
        assert response.status == "SUCCESS", f"Expected SUCCESS but got {response.status}: {response.errors}"
        assert "code" in response.data
        
        # Generated code should be present
        code = response.data["code"]
        assert len(code) > 0


@pytest.mark.asyncio
@skip_if_no_llm
async def test_coder_generates_typescript():
    """Test that CoderAgent can generate TypeScript files."""
    coder = CoderAgent()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "app.ts")
        
        task = AgentTask(
            id="test-ts-1",
            type="code",
            payload={
                "description": "Create a TypeScript interface for a User",
                "file_path": file_path
            },
            context={}
        )
        
        response = await coder.process(task)
        
        # Should succeed (not fail due to Python AST validation)
        assert response.status == "SUCCESS", f"Expected SUCCESS but got {response.status}: {response.errors}"
        assert "code" in response.data
        
        # Generated code should be present
        code = response.data["code"]
        assert len(code) > 0


@pytest.mark.asyncio
@skip_if_no_llm
async def test_coder_generates_jsx():
    """Test that CoderAgent can generate JSX files."""
    coder = CoderAgent()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "Component.jsx")
        
        task = AgentTask(
            id="test-jsx-1",
            type="code",
            payload={
                "description": "Create a simple React component",
                "file_path": file_path
            },
            context={}
        )
        
        response = await coder.process(task)
        
        # Should succeed (not fail due to Python AST validation)
        assert response.status == "SUCCESS", f"Expected SUCCESS but got {response.status}: {response.errors}"
        assert "code" in response.data
        
        # Generated code should be present
        code = response.data["code"]
        assert len(code) > 0


@pytest.mark.asyncio
@skip_if_no_llm
async def test_coder_still_validates_python():
    """Test that Python code is still validated with AST parser."""
    coder = CoderAgent()
    
    # Note: This test depends on the LLM actually generating invalid Python
    # which is not guaranteed. It's here to document expected behavior.
    # In practice, the LLM usually generates valid Python.
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "test.py")
        
        task = AgentTask(
            id="test-py-validation",
            type="code",
            payload={
                "description": "Create a Python function",
                "file_path": file_path
            },
            context={}
        )
        
        response = await coder.process(task)
        
        # If it succeeds, the code should be valid Python
        if response.status == "SUCCESS":
            code = response.data["code"]
            # Try to compile it - should not raise SyntaxError
            try:
                compile(code, '<string>', 'exec')
            except SyntaxError as e:
                pytest.fail(f"Generated Python code has syntax errors: {e}")


@pytest.mark.asyncio
async def test_language_detection_from_extension():
    """Test that language is correctly detected from file extension."""
    coder = CoderAgent()
    
    test_cases = [
        ("test.html", "HTML", "html"),
        ("test.css", "CSS", "css"),
        ("test.js", "JavaScript", "javascript"),
        ("test.py", "Python", "python"),
        ("test.ts", "TypeScript", "typescript"),
        ("test.jsx", "React JSX", "jsx"),
    ]
    
    for file_path, expected_lang, expected_tag in test_cases:
        detected_lang, detected_tag = coder._detect_language_from_path(file_path)
        assert detected_lang == expected_lang, f"Expected {expected_lang} for {file_path}, got {detected_lang}"
        assert detected_tag == expected_tag, f"Expected {expected_tag} for {file_path}, got {detected_tag}"


@pytest.mark.asyncio
async def test_empty_code_fails_validation():
    """Test that empty/whitespace code fails validation for non-Python languages."""
    from aegis.core.llm_response_parser import LLMResponseParser
    
    parser = LLMResponseParser()
    
    # Empty code should fail for non-Python languages
    for language in ['html', 'css', 'javascript']:
        is_valid, error = parser.validate_code("", language=language)
        assert not is_valid, f"Empty code should fail validation for {language}"
        assert "empty" in error.lower()
        
        # Whitespace-only should also fail
        is_valid, error = parser.validate_code("   \n  \t  ", language=language)
        assert not is_valid, f"Whitespace-only code should fail validation for {language}"
        assert "empty" in error.lower()
    
    # For Python, empty string should fail the basic sanity check
    is_valid, error = parser.validate_code("", language='python')
    assert not is_valid, "Empty code should fail validation for Python"
    
    # Whitespace-only Python is technically valid (empty module) in AST
    # but should fail the basic sanity check before AST parsing
    is_valid, error = parser.validate_code("   \n  \t  ", language='python')
    assert not is_valid, "Whitespace-only code should fail basic sanity check"
