"""Integration tests for semantic verification with iteration loop.

This test file validates the complete flow:
1. Code generation creates files with integration issues
2. Semantic verification detects the issues
3. Orchestrator regenerates files with error context
4. Second iteration produces correct, integrated code
"""

import pytest
from pathlib import Path
from aegis.core.code_verifier import verify_generated_code


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for testing."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    return workspace


class TestVerificationIterationFlow:
    """Test the complete verification and iteration flow."""
    
    def test_verification_detects_then_regenerates(self, temp_workspace):
        """Test that verification errors trigger regeneration."""
        # Simulate first attempt with integration issues
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
    <script src="app.js"></script>
</head>
<body>
    <form id="myform">
        <button type="submit">Submit</button>
    </form>
</body>
</html>
""")
        
        js_file = temp_workspace / "app.js"
        js_file.write_text("""
class MyApp {
    constructor() {
        this.data = [];
    }
}

export default MyApp;  // ES6 export without type="module"
""")
        
        css_file = temp_workspace / "styles.css"
        css_file.write_text("""
.container {
    width: 100%;
}

.button {
    padding: 10px;
}

.header {
    font-size: 24px;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"},
            {"path": "styles.css", "purpose": "CSS"}
        ]
        
        # First verification should fail
        result = verify_generated_code(temp_workspace, file_specs)
        assert not result.passed, "First attempt should fail verification"
        
        # Should have semantic errors
        semantic_feedback = result.get_semantic_feedback()
        assert semantic_feedback["has_semantic_errors"], "Should have semantic errors"
        assert semantic_feedback["error_count"] > 0, "Should have error count > 0"
        
        # Check that we have errors in each category
        assert len(semantic_feedback["categories"]["module_system"]) > 0, "Should detect ES6 module issue"
        assert len(semantic_feedback["categories"]["css_integration"]) > 0, "Should detect CSS class mismatch"
        assert len(semantic_feedback["categories"]["form_handlers"]) > 0, "Should detect missing form handler"
        
        # Should have actionable guidance
        assert len(semantic_feedback["guidance"]) > 0, "Should provide guidance"
        
        # Simulate second attempt with fixes
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
    <script src="app.js"></script>
</head>
<body>
    <div class="container">
        <h1 class="header">My App</h1>
        <form id="myform" onsubmit="return handleSubmit()">
            <button type="submit" class="button">Submit</button>
        </form>
    </div>
</body>
</html>
""")
        
        js_file.write_text("""
function handleSubmit() {
    console.log('Form submitted');
    return false;
}

// Global functions instead of ES6 exports
window.MyApp = {
    data: [],
    init: function() {
        console.log('App initialized');
    }
};
""")
        
        # Second verification should pass
        result2 = verify_generated_code(temp_workspace, file_specs)
        assert result2.passed, f"Second attempt should pass verification. Errors: {[e.message for e in result2.critical_errors]}"
        
        # Semantic feedback should show no errors
        semantic_feedback2 = result2.get_semantic_feedback()
        assert not semantic_feedback2["has_semantic_errors"], "Should have no semantic errors after fix"
        assert semantic_feedback2["error_count"] == 0, "Error count should be 0"


class TestSemanticFeedbackContent:
    """Test the semantic feedback content and guidance."""
    
    def test_es6_module_feedback(self, temp_workspace):
        """Test feedback for ES6 module issues."""
        html_file = temp_workspace / "index.html"
        html_file.write_text('<html><head><script src="app.js"></script></head></html>')
        
        js_file = temp_workspace / "app.js"
        js_file.write_text("export default class App {}")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        feedback = result.get_semantic_feedback()
        
        assert len(feedback["categories"]["module_system"]) > 0
        assert any("type=\"module\"" in g for g in feedback["guidance"])
    
    def test_css_integration_feedback(self, temp_workspace):
        """Test feedback for CSS integration issues."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div>No classes here</div>
</body>
</html>
""")
        
        css_file = temp_workspace / "styles.css"
        css_file.write_text("""
.container { width: 100%; }
.header { font-size: 24px; }
.button { padding: 10px; }
.footer { margin-top: 20px; }
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "styles.css", "purpose": "CSS"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        feedback = result.get_semantic_feedback()
        
        assert len(feedback["categories"]["css_integration"]) > 0
        assert any("class" in g.lower() for g in feedback["guidance"])
    
    def test_form_handler_feedback(self, temp_workspace):
        """Test feedback for form handler issues."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<body>
    <form id="myform">
        <input type="text" name="username">
        <button type="submit">Submit</button>
    </form>
</body>
</html>
""")
        
        file_specs = [{"path": "index.html", "purpose": "HTML"}]
        
        result = verify_generated_code(temp_workspace, file_specs)
        feedback = result.get_semantic_feedback()
        
        assert len(feedback["categories"]["form_handlers"]) > 0
        assert any("form" in g.lower() or "submit" in g.lower() for g in feedback["guidance"])


class TestMultipleIterations:
    """Test multiple iteration scenarios."""
    
    def test_partial_fix_then_complete_fix(self, temp_workspace):
        """Test that partial fixes still trigger another iteration."""
        # First attempt: all three issues
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<html>
<head>
    <link href="styles.css" rel="stylesheet">
    <script src="app.js"></script>
</head>
<body>
    <form><button type="submit">Go</button></form>
</body>
</html>
""")
        
        js_file = temp_workspace / "app.js"
        js_file.write_text("export default class App {}")
        
        css_file = temp_workspace / "styles.css"
        css_file.write_text(".container { width: 100%; }")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"},
            {"path": "styles.css", "purpose": "CSS"}
        ]
        
        result1 = verify_generated_code(temp_workspace, file_specs)
        assert not result1.passed
        errors1 = len(result1.critical_errors)
        
        # Second attempt: fix only ES6 export issue
        js_file.write_text("function init() {}")
        
        result2 = verify_generated_code(temp_workspace, file_specs)
        errors2 = len(result2.critical_errors)
        
        # Should have fewer errors but not pass yet
        assert errors2 < errors1, "Should have fewer errors after partial fix"
        assert not result2.passed, "Should still fail with remaining issues"
        
        # Third attempt: fix all issues
        html_file.write_text("""
<html>
<head>
    <link href="styles.css" rel="stylesheet">
    <script src="app.js"></script>
</head>
<body>
    <div class="container">
        <form onsubmit="return handleSubmit()">
            <button type="submit">Go</button>
        </form>
    </div>
</body>
</html>
""")
        
        js_file.write_text("""
function init() {
    console.log('initialized');
}

function handleSubmit() {
    return false;
}
""")
        
        result3 = verify_generated_code(temp_workspace, file_specs)
        assert result3.passed, "Should pass after all fixes"


class TestGuidanceQuality:
    """Test that guidance is helpful and actionable."""
    
    def test_guidance_is_actionable(self, temp_workspace):
        """Test that guidance provides clear next steps."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<html>
<head>
    <script src="app.js"></script>
</head>
<body>
    <button onclick="handleClick()">Click</button>
</body>
</html>
""")
        
        js_file = temp_workspace / "app.js"
        js_file.write_text("export default { handleClick() {} }")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        feedback = result.get_semantic_feedback()
        
        # Check that guidance provides specific actions
        guidance_text = " ".join(feedback["guidance"]).lower()
        
        # Should mention specific solutions
        assert "type=\"module\"" in guidance_text or "global" in guidance_text
        assert "window" in guidance_text or "export" in guidance_text
        
    def test_guidance_not_duplicated(self, temp_workspace):
        """Test that same guidance isn't repeated multiple times."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<html>
<head>
    <script src="app1.js"></script>
    <script src="app2.js"></script>
    <script src="app3.js"></script>
</head>
</html>
""")
        
        for i in range(1, 4):
            js_file = temp_workspace / f"app{i}.js"
            js_file.write_text(f"export default class App{i} {{}}")
        
        file_specs = [{"path": "index.html", "purpose": "HTML"}]
        file_specs.extend([
            {"path": f"app{i}.js", "purpose": f"JS {i}"} for i in range(1, 4)
        ])
        
        result = verify_generated_code(temp_workspace, file_specs)
        feedback = result.get_semantic_feedback()
        
        # Even with 3 files with the same issue, guidance should not be tripled
        guidance_count = len(feedback["guidance"])
        assert guidance_count <= 5, "Guidance should be deduplicated"
