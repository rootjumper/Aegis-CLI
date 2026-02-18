"""Tests for enhanced Layer 3 semantic verification.

This test file validates the new semantic checks added to catch
integration issues between HTML, JavaScript, and CSS files.
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


class TestES6ModuleVerification:
    """Test ES6 module export/import verification."""
    
    def test_es6_export_without_module_type(self, temp_workspace):
        """Test detection of ES6 exports loaded without type='module'."""
        # HTML without type="module"
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="calculator.js"></script>
</head>
<body>
    <button onclick="calculate()">Calculate</button>
</body>
</html>
""")
        
        # JavaScript with ES6 export
        js_file = temp_workspace / "calculator.js"
        js_file.write_text("""
class Calculator {
    calculate() {
        return 42;
    }
}

export default Calculator;
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "calculator.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should error about ES6 export without type="module"
        assert not result.passed
        es6_errors = [e for e in result.critical_errors if "ES6" in e.message or "module" in e.message.lower()]
        assert len(es6_errors) > 0
        assert any("type=\"module\"" in e.message for e in es6_errors)
    
    def test_es6_export_with_module_type_passes(self, temp_workspace):
        """Test that ES6 exports with type='module' don't trigger errors."""
        # HTML WITH type="module"
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script type="module" src="calculator.js"></script>
</head>
<body>
    <div id="app"></div>
</body>
</html>
""")
        
        # JavaScript with ES6 export
        js_file = temp_workspace / "calculator.js"
        js_file.write_text("""
class Calculator {
    calculate() {
        return 42;
    }
}

export default Calculator;
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "calculator.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should NOT error about ES6 exports (type="module" is present)
        es6_errors = [e for e in result.critical_errors if "ES6" in e.message or "export" in e.message.lower()]
        assert len(es6_errors) == 0
    
    def test_global_functions_without_module_type_passes(self, temp_workspace):
        """Test that global functions work fine without type='module'."""
        # HTML without type="module"
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="calculator.js"></script>
</head>
<body>
    <button onclick="calculate()">Calculate</button>
</body>
</html>
""")
        
        # JavaScript with global function (no export)
        js_file = temp_workspace / "calculator.js"
        js_file.write_text("""
function calculate() {
    return 42;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "calculator.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass - global functions work without type="module"
        es6_errors = [e for e in result.critical_errors if "ES6" in e.message or "module" in e.message.lower()]
        assert len(es6_errors) == 0


class TestHTMLCSSIntegration:
    """Test HTML-CSS class integration verification."""
    
    def test_css_classes_not_used_in_html(self, temp_workspace):
        """Test detection of CSS classes that aren't used in HTML."""
        # HTML without any classes
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div>
        <input type="text">
        <button>Calculate</button>
    </div>
</body>
</html>
""")
        
        # CSS with many classes
        css_file = temp_workspace / "styles.css"
        css_file.write_text("""
.calculator {
    width: 300px;
}

.display {
    padding: 10px;
}

.button {
    margin: 5px;
}

.operator {
    color: blue;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "styles.css", "purpose": "CSS"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should error about unused CSS classes
        assert not result.passed
        css_errors = [e for e in result.critical_errors if "CSS" in e.message or "class" in e.message.lower()]
        assert len(css_errors) > 0
    
    def test_html_uses_css_classes_passes(self, temp_workspace):
        """Test that HTML using CSS classes doesn't trigger errors."""
        # HTML with classes matching CSS
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="calculator">
        <input type="text" class="display">
        <button class="button">Calculate</button>
    </div>
</body>
</html>
""")
        
        # CSS with matching classes
        css_file = temp_workspace / "styles.css"
        css_file.write_text("""
.calculator {
    width: 300px;
}

.display {
    padding: 10px;
}

.button {
    margin: 5px;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "styles.css", "purpose": "CSS"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass - HTML uses CSS classes
        css_errors = [e for e in result.critical_errors if "class" in e.message.lower() and "not used" in e.message.lower()]
        assert len(css_errors) == 0
    
    def test_partial_class_usage_allowed(self, temp_workspace):
        """Test that partial CSS class usage is allowed (utility classes)."""
        # HTML using some classes
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="calculator">
        <input type="text" class="display">
    </div>
</body>
</html>
""")
        
        # CSS with more classes (some unused)
        css_file = temp_workspace / "styles.css"
        css_file.write_text("""
.calculator {
    width: 300px;
}

.display {
    padding: 10px;
}

.hidden {
    display: none;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "styles.css", "purpose": "CSS"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass - some classes unused is OK (utility classes, responsive classes, etc.)
        # Only fails if >50% unused
        css_errors = [e for e in result.critical_errors if "class" in e.message.lower()]
        assert len(css_errors) == 0


class TestFormHandlerVerification:
    """Test form submission handler verification."""
    
    def test_form_without_submit_handler(self, temp_workspace):
        """Test detection of forms with submit buttons but no handler."""
        # HTML with form but no onsubmit
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<body>
    <form id="calculator-form">
        <input type="number" id="num1">
        <input type="number" id="num2">
        <button type="submit">Calculate</button>
    </form>
</body>
</html>
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should error about missing form handler
        assert not result.passed
        form_errors = [e for e in result.critical_errors if "form" in e.message.lower() or "submit" in e.message.lower()]
        assert len(form_errors) > 0
    
    def test_form_with_onsubmit_handler_passes(self, temp_workspace):
        """Test that forms with onsubmit handlers don't trigger errors."""
        # HTML with form and onsubmit
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <script src="calculator.js"></script>
</head>
<body>
    <form id="calculator-form" onsubmit="return handleSubmit()">
        <input type="number" id="num1">
        <input type="number" id="num2">
        <button type="submit">Calculate</button>
    </form>
</body>
</html>
""")
        
        js_file = temp_workspace / "calculator.js"
        js_file.write_text("""
function handleSubmit() {
    // Form submission logic
    return false;
}
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"},
            {"path": "calculator.js", "purpose": "JavaScript"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass - form has onsubmit handler
        form_errors = [e for e in result.critical_errors if "form" in e.message.lower() and "handler" in e.message.lower()]
        assert len(form_errors) == 0
    
    def test_form_without_submit_button_passes(self, temp_workspace):
        """Test that forms without submit buttons don't trigger errors."""
        # HTML with form but no submit button (e.g., AJAX form)
        html_file = temp_workspace / "index.html"
        html_file.write_text("""
<!DOCTYPE html>
<html>
<body>
    <form id="search-form">
        <input type="text" id="query">
        <button type="button" onclick="search()">Search</button>
    </form>
</body>
</html>
""")
        
        file_specs = [
            {"path": "index.html", "purpose": "HTML"}
        ]
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should pass - no submit button, so no handler needed
        form_errors = [e for e in result.critical_errors if "submit" in e.message.lower()]
        # This form doesn't have a submit button, so it shouldn't error
        assert len(form_errors) == 0


class TestCalculatorAppScenario:
    """Test the exact scenario from the problem statement."""
    
    def test_calculator_app_integration_issues(self, temp_workspace):
        """Test detection of all three issues from calculator app example."""
        # Issue 1: HTML expects form-based, JS provides class-based with exports
        html_file = temp_workspace / "src" / "calculator.html"
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text("""
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="css/styles.css">
    <script src="js/calculator.js"></script>
</head>
<body>
    <form id="calculator-form">
        <input type="number" id="num1">
        <select id="operator">
            <option value="+">+</option>
            <option value="-">-</option>
        </select>
        <input type="number" id="num2">
        <button type="submit">Calculate</button>
    </form>
</body>
</html>
""")
        
        # Issue 2: CSS defines classes not used in HTML
        css_file = temp_workspace / "src" / "css" / "styles.css"
        css_file.parent.mkdir(parents=True, exist_ok=True)
        css_file.write_text("""
.display {
    width: 100%;
    padding: 10px;
}

.container {
    max-width: 400px;
    margin: 0 auto;
}

.button {
    padding: 10px;
    margin: 5px;
}

.operator {
    color: blue;
}
""")
        
        # Issue 3: JavaScript uses ES6 exports without type="module"
        js_file = temp_workspace / "src" / "js" / "calculator.js"
        js_file.parent.mkdir(parents=True, exist_ok=True)
        js_file.write_text("""
class Calculator {
    calculateResult() {
        // calculation logic
    }
    
    handleDigitPress() {
        // digit press logic
    }
    
    clearDisplay() {
        // clear logic
    }
}

const calculator = new Calculator();
export default calculator;
""")
        
        file_specs = [
            {"path": "src/calculator.html", "purpose": "Main HTML page"},
            {"path": "src/css/styles.css", "purpose": "Styles"},
            {"path": "src/js/calculator.js", "purpose": "Calculator logic"}
        ]
        
        result = verify_generated_code(temp_workspace, file_specs)
        
        # Should fail with multiple errors
        assert not result.passed
        
        # Should have ES6 module error
        es6_errors = [e for e in result.critical_errors if "ES6" in e.message or "export" in e.message.lower()]
        assert len(es6_errors) > 0, "Should detect ES6 export without type='module'"
        
        # Should have CSS class mismatch error
        css_errors = [e for e in result.critical_errors if "CSS" in e.message and "class" in e.message.lower()]
        assert len(css_errors) > 0, "Should detect CSS classes not used in HTML"
        
        # Should have form handler error
        form_errors = [e for e in result.critical_errors if "form" in e.message.lower()]
        assert len(form_errors) > 0, "Should detect form without submission handler"
        
        # Verify we caught all three critical integration issues
        assert len(result.critical_errors) >= 3, f"Should catch at least 3 critical errors, got {len(result.critical_errors)}"
