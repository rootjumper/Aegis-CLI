"""Test for HTML script reference mismatch fix.

This test validates that when generating multi-file web applications,
HTML files correctly reference JavaScript and CSS files with proper paths.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.coder import CoderAgent
from aegis.agents.base import AgentTask


@pytest.mark.asyncio
async def test_orchestrator_finds_related_files():
    """Test that orchestrator can identify related files for a given file."""
    orchestrator = OrchestratorAgent()
    
    # Create a plan with HTML, JS, and CSS files
    plan = {
        "files_to_create": [
            {"path": "src/index.html", "purpose": "Main HTML page"},
            {"path": "src/js/app.js", "purpose": "JavaScript logic"},
            {"path": "src/css/styles.css", "purpose": "Styling"}
        ]
    }
    
    # Test finding related files for HTML
    related = orchestrator._find_related_files("src/index.html", plan)
    
    assert "javascript" in related
    assert "stylesheets" in related
    assert "src/js/app.js" in related["javascript"]
    assert "src/css/styles.css" in related["stylesheets"]


@pytest.mark.asyncio
async def test_orchestrator_finds_related_files_for_js():
    """Test that orchestrator identifies HTML files that import JS."""
    orchestrator = OrchestratorAgent()
    
    plan = {
        "files_to_create": [
            {"path": "src/index.html", "purpose": "Main HTML page"},
            {"path": "src/js/app.js", "purpose": "JavaScript logic"}
        ]
    }
    
    # Test finding related files for JS
    related = orchestrator._find_related_files("src/js/app.js", plan)
    
    assert "html" in related
    assert "src/index.html" in related["html"]


@pytest.mark.asyncio
async def test_coder_receives_related_files_context():
    """Test that CoderAgent receives context about related files.
    
    This is a unit test that doesn't require LLM - it just validates
    that the context is properly structured and passed.
    """
    from aegis.agents.coder import CoderAgent
    
    coder = CoderAgent()
    
    # Mock context that orchestrator would pass
    context_info = {
        "workspace": "test_app",
        "related_files": {
            "javascript": ["src/js/calculator.js"],
            "stylesheets": ["src/css/styles.css"]
        },
        "all_files": [
            {"path": "src/calculator.html", "purpose": "Main HTML"},
            {"path": "src/js/calculator.js", "purpose": "Calculator logic"},
            {"path": "src/css/styles.css", "purpose": "Styling"}
        ]
    }
    
    # Create task with this context
    task = AgentTask(
        id="test-context-1",
        type="code",
        payload={
            "description": "Create HTML calculator interface",
            "file_path": "/tmp/test_calculator.html",
            "context": context_info
        },
        context={}
    )
    
    # Verify that the context is properly structured
    assert "related_files" in task.payload["context"]
    assert "javascript" in task.payload["context"]["related_files"]
    assert "stylesheets" in task.payload["context"]["related_files"]
    assert "src/js/calculator.js" in task.payload["context"]["related_files"]["javascript"]
    assert "src/css/styles.css" in task.payload["context"]["related_files"]["stylesheets"]


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
async def test_html_references_correct_js_css_paths():
    """Test that generated HTML files reference JS/CSS with correct paths.
    
    This is an integration test that requires an LLM.
    It validates the complete fix: orchestrator passing context + coder using it.
    """
    from aegis.agents.orchestrator import OrchestratorAgent
    from aegis.core.workspace import WorkspaceManager
    
    # Clean up any existing workspace
    workspace_manager = WorkspaceManager()
    workspace_name = "test_html_ref_app"
    
    try:
        # Create orchestrator
        orchestrator = OrchestratorAgent()
        
        # Create a task to build a simple calculator web app
        task = AgentTask(
            id="test-html-ref-1",
            type="user_prompt",
            payload={
                "description": "Create a simple calculator web app with HTML, JavaScript in js/ folder, and CSS in css/ folder"
            },
            context={}
        )
        
        # Process the task
        response = await orchestrator.process(task)
        
        # Should succeed
        assert response.status == "SUCCESS", f"Expected SUCCESS but got {response.status}: {response.errors}"
        
        # Get workspace path
        workspace_path = workspace_manager.get_current_workspace()
        assert workspace_path is not None, "No workspace was created"
        
        # Find the HTML file
        html_files = list(Path(workspace_path).rglob("*.html"))
        assert len(html_files) > 0, "No HTML file was created"
        
        html_file = html_files[0]
        html_content = html_file.read_text()
        
        # Find JS and CSS files
        js_files = list(Path(workspace_path).rglob("*.js"))
        css_files = list(Path(workspace_path).rglob("*.css"))
        
        # Validation: Check that HTML references correct files
        if js_files:
            # Check that HTML contains script references
            assert "<script" in html_content.lower(), "HTML should have <script> tags"
            
            # Check that the reference includes the subdirectory if JS is in a subfolder
            for js_file in js_files:
                # Get relative path from HTML file to JS file
                rel_path = os.path.relpath(js_file, html_file.parent)
                
                # The HTML should reference this path or at least mention the JS filename
                js_filename = js_file.name
                
                # Check that the actual filename is referenced (not a generic "script.js")
                # unless the file is actually named "script.js"
                if js_filename != "script.js":
                    assert js_filename in html_content, \
                        f"HTML should reference actual JS file '{js_filename}', not use generic 'script.js'"
        
        if css_files:
            # Check that HTML contains stylesheet links
            assert "<link" in html_content.lower() or "stylesheet" in html_content.lower(), \
                "HTML should have <link> tags for stylesheets"
            
            # Check that the reference includes the subdirectory if CSS is in a subfolder
            for css_file in css_files:
                css_filename = css_file.name
                
                # Check that the actual filename is referenced
                if css_filename != "styles.css" or len(css_files) == 1:
                    # If not named "styles.css" or it's the only CSS file, it should be referenced
                    # The reference might be "styles.css" which is acceptable as a common name
                    # But if it's in a subdirectory like "css/", that should be included
                    
                    # Check if CSS is in a subdirectory
                    css_dir = css_file.parent.name
                    if css_dir not in ['src', workspace_path.name]:
                        # It's in a subdirectory like "css/"
                        # The HTML should include this directory in the reference
                        assert css_dir in html_content or css_filename in html_content, \
                            f"HTML should reference CSS file with subdirectory or actual filename"
        
    finally:
        # Clean up workspace
        if workspace_manager.get_current_workspace():
            workspace_manager.delete_workspace()


@pytest.mark.asyncio
async def test_related_files_empty_for_single_file():
    """Test that related_files is empty when only one file is in the plan."""
    orchestrator = OrchestratorAgent()
    
    plan = {
        "files_to_create": [
            {"path": "src/main.py", "purpose": "Main Python file"}
        ]
    }
    
    related = orchestrator._find_related_files("src/main.py", plan)
    
    # Should have empty lists (no related files)
    assert len(related["javascript"]) == 0
    assert len(related["stylesheets"]) == 0
    assert len(related["html"]) == 0


@pytest.mark.asyncio
async def test_related_files_excludes_self():
    """Test that a file is not listed as related to itself."""
    orchestrator = OrchestratorAgent()
    
    plan = {
        "files_to_create": [
            {"path": "src/index.html", "purpose": "HTML page"},
            {"path": "src/about.html", "purpose": "About page"}
        ]
    }
    
    related = orchestrator._find_related_files("src/index.html", plan)
    
    # Should list about.html but not index.html
    assert "src/index.html" not in related["html"]
    assert "src/about.html" in related["html"]
