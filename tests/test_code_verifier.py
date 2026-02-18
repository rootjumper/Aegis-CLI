"""Tests for code verification module."""

import pytest
from pathlib import Path
from aegis.core.code_verifier import (
    CodeVerifier,
    VerificationResult,
    VerificationIssue,
    verify_generated_code
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Create temporary workspace for testing."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    return workspace


class TestLayer1FileStructure:
    """Test Layer 1: File Structure Verification."""
    
    def test_file_exists_check(self, temp_workspace):
        """Test that verifier catches missing files."""
        file_specs = [
            {"path": "missing.py", "purpose": "Test file"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        
        assert not result.passed
        assert len(result.critical_errors) > 0
        assert any("does not exist" in issue.message for issue in result.critical_errors)
    
    def test_empty_file_check(self, temp_workspace):
        """Test that verifier catches empty files."""
        # Create empty file
        empty_file = temp_workspace / "empty.py"
        empty_file.write_text("")
        
        file_specs = [
            {"path": "empty.py", "purpose": "Empty file"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        
        assert not result.passed
        assert any("empty" in issue.message.lower() for issue in result.critical_errors)
    
    def test_file_with_content_passes(self, temp_workspace):
        """Test that files with content pass structure check."""
        # Create file with content
        code_file = temp_workspace / "valid.py"
        code_file.write_text("def hello():\n    print('Hello')\n")
        
        file_specs = [
            {"path": "valid.py", "purpose": "Valid Python file"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass Layer 1 (structure)
        assert "valid.py" in result.file_checks
        assert result.file_checks["valid.py"]["exists"]
        assert result.file_checks["valid.py"]["size"] > 0


class TestLayer2StaticAnalysis:
    """Test Layer 2: Static Code Analysis."""
    
    def test_python_syntax_error(self, temp_workspace):
        """Test detection of Python syntax errors."""
        bad_python = temp_workspace / "bad.py"
        bad_python.write_text("def hello(\n    print('missing closing paren')\n")
        
        file_specs = [{"path": "bad.py", "purpose": "Bad Python"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        assert not result.passed
        assert any("syntax error" in issue.message.lower() for issue in result.critical_errors)
    
    def test_python_valid_syntax(self, temp_workspace):
        """Test that valid Python passes syntax check."""
        good_python = temp_workspace / "good.py"
        good_python.write_text("""
def calculate_sum(a: int, b: int) -> int:
    '''Calculate sum of two numbers.'''
    return a + b

class Calculator:
    def add(self, x, y):
        return x + y
""")
        
        file_specs = [{"path": "good.py", "purpose": "Valid Python"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should not have syntax errors
        syntax_errors = [e for e in result.critical_errors if "syntax" in e.message.lower()]
        assert len(syntax_errors) == 0
    
    def test_javascript_unbalanced_braces(self, temp_workspace):
        """Test detection of unbalanced braces in JavaScript."""
        bad_js = temp_workspace / "bad.js"
        bad_js.write_text("""
function test() {
    console.log('missing closing brace');
""")
        
        file_specs = [{"path": "bad.js", "purpose": "Bad JS"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        assert not result.passed
        assert any("unbalanced braces" in issue.message.lower() for issue in result.critical_errors)
    
    def test_javascript_valid_syntax(self, temp_workspace):
        """Test that valid JavaScript passes syntax check."""
        good_js = temp_workspace / "good.js"
        good_js.write_text("""
function calculateTotal(items) {
    return items.reduce((sum, item) => sum + item.price, 0);
}

const double = (x) => x * 2;
""")
        
        file_specs = [{"path": "good.js", "purpose": "Valid JS"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should not have syntax errors for braces/parens
        brace_errors = [e for e in result.critical_errors if "brace" in e.message.lower()]
        assert len(brace_errors) == 0
    
    def test_html_parsing(self, temp_workspace):
        """Test HTML parsing and reference extraction."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
    <script src="app.js"></script>
</head>
<body>
    <button onclick="calculate()">Click</button>
</body>
</html>
""")
        
        file_specs = [{"path": "index.html", "purpose": "HTML file"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Check that references were extracted
        verifier = CodeVerifier(temp_workspace)
        verifier.verify(file_specs)
        
        assert "index.html" in verifier.symbol_table
        symbols = verifier.symbol_table["index.html"]
        assert "styles.css" in symbols["stylesheets"]
        assert "app.js" in symbols["scripts"]
        assert any(func == "calculate" for func, _ in symbols["functions_called"])
    
    def test_json_invalid_syntax(self, temp_workspace):
        """Test detection of invalid JSON."""
        bad_json = temp_workspace / "config.json"
        bad_json.write_text('{"key": "value",}')  # Trailing comma is invalid
        
        file_specs = [{"path": "config.json", "purpose": "Config"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        assert not result.passed
        assert any("invalid json" in issue.message.lower() for issue in result.critical_errors)
    
    def test_unfinished_code_markers(self, temp_workspace):
        """Test detection of TODO/FIXME markers."""
        todo_file = temp_workspace / "todo.py"
        todo_file.write_text("""
def process():
    # TODO: Implement this function
    pass
""")
        
        file_specs = [{"path": "todo.py", "purpose": "File with TODOs"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should be a warning, not an error
        assert any("unfinished" in w.message.lower() for w in result.warnings)


class TestLayer3SemanticVerification:
    """Test Layer 3: Semantic Verification (Cross-file)."""
    
    def test_html_missing_script_reference(self, temp_workspace):
        """Test detection of missing script files referenced in HTML."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="missing.js"></script>
</head>
<body></body>
</html>
""")
        
        file_specs = [{"path": "index.html", "purpose": "HTML"}]
        result = verify_generated_code(temp_workspace, file_specs)
        
        assert not result.passed
        assert any("missing.js" in issue.message for issue in result.critical_errors)
    
    def test_html_script_reference_exists(self, temp_workspace):
        """Test that existing script references don't trigger errors."""
        # Create both HTML and JS files
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="app.js"></script>
</head>
<body></body>
</html>
""")
        
        js_file = temp_workspace / "app.js"
        js_file.write_text("console.log('Hello');")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should not have missing reference errors
        missing_errors = [e for e in result.critical_errors if "not found" in e.message]
        assert len(missing_errors) == 0
    
    def test_html_function_call_verification(self, temp_workspace):
        """Test verification of functions called in HTML event handlers."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="app.js"></script>
</head>
<body>
    <button onclick="calculateResult()">Calculate</button>
</body>
</html>
""")
        
        # JS file without the function
        js_file = temp_workspace / "app.js"
        js_file.write_text("console.log('No calculateResult function here');")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should error about missing function (upgraded from warning to error for Layer 3)
        assert any("calculateResult" in e.message for e in result.critical_errors)
    
    def test_html_function_exists_in_js(self, temp_workspace):
        """Test that functions found in JS don't trigger warnings."""
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="app.js"></script>
</head>
<body>
    <button onclick="calculateResult()">Calculate</button>
</body>
</html>
""")
        
        # JS file WITH the function
        js_file = temp_workspace / "app.js"
        js_file.write_text("""
function calculateResult() {
    return 42;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "app.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should NOT warn about missing function
        calc_warnings = [w for w in result.warnings if "calculateResult" in w.message]
        assert len(calc_warnings) == 0


class TestVerificationResult:
    """Test VerificationResult functionality."""
    
    def test_passed_with_no_errors(self):
        """Test that result passes with no errors."""
        result = VerificationResult(passed=True)
        assert result.passed
        assert len(result.critical_errors) == 0
    
    def test_failed_with_errors(self):
        """Test that result fails with errors."""
        result = VerificationResult(passed=False)
        result.issues.append(VerificationIssue(
            severity="error",
            layer=1,
            file_path="test.py",
            line_number=10,
            message="Test error"
        ))
        
        assert not result.passed
        assert len(result.critical_errors) == 1
    
    def test_summary_generation(self):
        """Test summary generation."""
        result = VerificationResult(passed=False)
        result.issues.append(VerificationIssue(
            severity="error",
            layer=2,
            file_path="test.py",
            line_number=5,
            message="Syntax error"
        ))
        result.warnings.append(VerificationIssue(
            severity="warning",
            layer=3,
            file_path="test.js",
            line_number=None,
            message="Unused variable"
        ))
        
        summary = result.get_summary()
        
        assert "FAILED" in summary
        assert "Critical Errors: 1" in summary
        assert "Warnings: 1" in summary
        assert "Syntax error" in summary
    
    def test_auto_fixable_errors(self):
        """Test filtering of auto-fixable errors."""
        result = VerificationResult(passed=False)
        result.issues.append(VerificationIssue(
            severity="error",
            layer=3,
            file_path="index.html",
            line_number=None,
            message="Missing reference",
            auto_fixable=True
        ))
        result.issues.append(VerificationIssue(
            severity="error",
            layer=2,
            file_path="test.py",
            line_number=1,
            message="Syntax error",
            auto_fixable=False
        ))
        
        fixable = result.auto_fixable_errors
        assert len(fixable) == 1
        assert fixable[0].auto_fixable


class TestCompleteWorkflow:
    """Test complete verification workflows."""
    
    def test_simple_html_css_js_project(self, temp_workspace):
        """Test verification of a simple web project."""
        # Create HTML
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Calculator</title>
    <link rel="stylesheet" href="styles.css">
    <script src="calculator.js"></script>
</head>
<body>
    <div id="calculator">
        <input type="text" id="display">
        <button onclick="calculate()">Calculate</button>
    </div>
</body>
</html>
""")
        
        # Create CSS
        css_file = temp_workspace / "styles.css"
        css_file.write_text("""
#calculator {
    width: 300px;
    margin: 50px auto;
}

#display {
    width: 100%;
    padding: 10px;
}
""")
        
        # Create JS
        js_file = temp_workspace / "calculator.js"
        js_file.write_text("""
function calculate() {
    const display = document.getElementById('display');
    const result = eval(display.value);
    display.value = result;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "Main HTML page"},
            {"path": "styles.css", "purpose": "Styles"},
            {"path": "calculator.js", "purpose": "Calculator logic"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        
        # All files should exist
        assert all(path in result.file_checks for path in ["index.html", "styles.css", "calculator.js"])
        
        # Should pass (no missing references, function exists)
        assert result.passed or len(result.critical_errors) == 0
    
    def test_python_project_with_imports(self, temp_workspace):
        """Test verification of Python project with imports."""
        # Create main module
        main_file = temp_workspace / "main.py"
        main_file.write_text("""
from pathlib import Path
import utils

def process():
    helper = utils.Helper()
    return helper.process()
""")
        
        # Create utils module
        utils_file = temp_workspace / "utils.py"
        utils_file.write_text("""
class Helper:
    def process(self):
        return "processed"
""")
        
        file_specs = [
            {"path": "main.py", "purpose": "Main module"},
            {"path": "utils.py", "purpose": "Utilities"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass - utils is found
        assert result.passed or len(result.critical_errors) == 0
