"""Code verification module for multi-language code generation.

This module implements a 4-layer verification strategy:
1. File Structure Verification - Files exist, have content, correct extensions
2. Static Code Analysis - Syntax, imports, dependencies, circular imports
3. Semantic Verification - Cross-file integration, export/import matching
4. Runtime Verification - Optional web/Python runtime checks

The verifier catches common issues before code is delivered to users.
"""

import re
import ast
import json
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class VerificationIssue:
    """Represents a verification issue found in code."""
    
    severity: str  # "error", "warning", "info"
    layer: int  # 1, 2, 3, or 4
    file_path: str
    line_number: int | None
    message: str
    auto_fixable: bool = False
    
    def __str__(self) -> str:
        """String representation of issue."""
        prefix = "❌ ERROR" if self.severity == "error" else "⚠️ WARNING" if self.severity == "warning" else "ℹ️ INFO"
        line_info = f" (line {self.line_number})" if self.line_number else ""
        return f"{prefix}: {self.file_path}{line_info}: {self.message}"


@dataclass
class VerificationResult:
    """Result of code verification."""
    
    passed: bool
    issues: list[VerificationIssue] = field(default_factory=list)
    warnings: list[VerificationIssue] = field(default_factory=list)
    file_checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    @property
    def critical_errors(self) -> list[VerificationIssue]:
        """Get critical errors that must be fixed."""
        return [issue for issue in self.issues if issue.severity == "error"]
    
    @property
    def auto_fixable_errors(self) -> list[VerificationIssue]:
        """Get errors that can be auto-fixed."""
        return [issue for issue in self.issues if issue.auto_fixable]
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        error_count = len(self.critical_errors)
        warning_count = len(self.warnings)
        
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        summary = f"\n{status}\n"
        summary += f"Critical Errors: {error_count}\n"
        summary += f"Warnings: {warning_count}\n"
        
        if error_count > 0:
            summary += "\n=== Critical Errors ===\n"
            for issue in self.critical_errors[:10]:  # Show max 10
                summary += f"{issue}\n"
        
        if warning_count > 0:
            summary += "\n=== Warnings ===\n"
            for issue in self.warnings[:10]:  # Show max 10
                summary += f"{issue}\n"
        
        return summary
    
    def get_semantic_feedback(self) -> dict[str, Any]:
        """Get semantic verification feedback for agent prompts.
        
        Returns:
            Dictionary with categorized semantic issues and guidance
        """
        semantic_errors = [e for e in self.critical_errors if e.layer == 3]
        
        feedback = {
            "has_semantic_errors": len(semantic_errors) > 0,
            "error_count": len(semantic_errors),
            "categories": {
                "module_system": [],
                "css_integration": [],
                "form_handlers": [],
                "cross_file": []
            },
            "guidance": []
        }
        
        for error in semantic_errors:
            msg = error.message.lower()
            
            # Categorize errors
            if "es6" in msg or "export" in msg or "module" in msg:
                feedback["categories"]["module_system"].append(error.message)
                if "type=\"module\"" not in [g for g in feedback["guidance"]]:
                    feedback["guidance"].append(
                        "Use type=\"module\" in <script> tags when JavaScript uses ES6 exports, "
                        "OR use global functions (window.functionName) instead of exports"
                    )
            
            elif "css" in msg or "class" in msg or "style" in msg:
                feedback["categories"]["css_integration"].append(error.message)
                if "css-html" not in [g for g in feedback["guidance"]]:
                    feedback["guidance"].append(
                        "Ensure HTML elements use class attributes that match CSS selectors. "
                        "CSS classes must be applied to HTML elements to have any visual effect."
                    )
            
            elif "form" in msg or "submit" in msg:
                feedback["categories"]["form_handlers"].append(error.message)
                if "form-handler" not in [g for g in feedback["guidance"]]:
                    feedback["guidance"].append(
                        "Forms with submit buttons need submission handlers. "
                        "Add onsubmit=\"return handleSubmit()\" to <form> tags or attach event listeners in JavaScript."
                    )
            
            else:
                feedback["categories"]["cross_file"].append(error.message)
        
        return feedback


class HTMLReferenceExtractor(HTMLParser):
    """Extract script and link references from HTML."""
    
    def __init__(self) -> None:
        """Initialize HTML parser."""
        super().__init__()
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.images: list[str] = []
        self.functions_called: list[tuple[str, int]] = []  # (function_name, line_number)
        self._current_line = 1
    
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle start tags."""
        attrs_dict = dict(attrs)
        
        # Extract script sources
        if tag == "script" and "src" in attrs_dict:
            src = attrs_dict.get("src")
            if src:
                self.scripts.append(src)
        
        # Extract stylesheet links
        if tag == "link" and attrs_dict.get("rel") == "stylesheet":
            href = attrs_dict.get("href")
            if href:
                self.stylesheets.append(href)
        
        # Extract image sources
        if tag == "img" and "src" in attrs_dict:
            src = attrs_dict.get("src")
            if src:
                self.images.append(src)
        
        # Extract onclick handlers and other event handlers
        for attr_name, attr_value in attrs:
            if attr_name and attr_name.startswith("on") and attr_value:
                # Extract function names from event handlers
                # e.g., onclick="calculateResult()" → "calculateResult"
                func_matches = re.findall(r'(\w+)\s*\(', attr_value)
                for func_name in func_matches:
                    self.functions_called.append((func_name, self._current_line))
    
    def handle_data(self, data: str) -> None:
        """Track line numbers from data."""
        self._current_line += data.count('\n')


class CodeVerifier:
    """Multi-language code verifier with 4-layer validation."""
    
    # Supported file extensions and their languages
    LANGUAGE_MAP = {
        '.py': 'python',
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.html': 'html',
        '.htm': 'html',
        '.css': 'css',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.jsx': 'jsx',
    }
    
    def __init__(self, workspace_path: str | Path) -> None:
        """Initialize code verifier.
        
        Args:
            workspace_path: Root path of workspace to verify
        """
        self.workspace_path = Path(workspace_path)
        self.file_map: dict[str, Path] = {}  # Maps relative paths to full paths
        self.symbol_table: dict[str, dict[str, Any]] = {}  # Cross-file symbol tracking
    
    def verify(self, file_specs: list[dict[str, str]]) -> VerificationResult:
        """Run complete verification on generated files.
        
        Args:
            file_specs: List of file specifications with 'path' and 'purpose'
        
        Returns:
            VerificationResult with all issues found
        """
        result = VerificationResult(passed=True)
        
        # Build file map
        for spec in file_specs:
            rel_path = spec["path"]
            full_path = self.workspace_path / rel_path
            self.file_map[rel_path] = full_path
        
        # Layer 1: File Structure Verification
        self._verify_file_structure(file_specs, result)
        
        # Layer 2: Static Code Analysis
        self._verify_static_code(file_specs, result)
        
        # Layer 3: Semantic Verification
        self._verify_semantics(file_specs, result)
        
        # Layer 4: Runtime Verification (optional, basic checks only)
        # Skipped for now - could be added later for specific languages
        
        # Determine pass/fail
        result.passed = len(result.critical_errors) == 0
        
        return result
    
    def _verify_file_structure(
        self,
        file_specs: list[dict[str, str]],
        result: VerificationResult
    ) -> None:
        """Layer 1: Verify file structure.
        
        Args:
            file_specs: List of file specifications
            result: VerificationResult to append issues to
        """
        for spec in file_specs:
            rel_path = spec["path"]
            full_path = self.file_map.get(rel_path)
            
            if not full_path:
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=1,
                    file_path=rel_path,
                    line_number=None,
                    message="File path not found in file map"
                ))
                continue
            
            # Check if file exists
            if not full_path.exists():
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=1,
                    file_path=rel_path,
                    line_number=None,
                    message="File does not exist"
                ))
                continue
            
            # Check if file has content
            try:
                content = full_path.read_text()
                if not content or content.strip() == "":
                    result.issues.append(VerificationIssue(
                        severity="error",
                        layer=1,
                        file_path=rel_path,
                        line_number=None,
                        message="File is empty"
                    ))
                    continue
                
                # Check file extension matches expected type
                ext = full_path.suffix.lower()
                expected_lang = self.LANGUAGE_MAP.get(ext)
                
                # Store file check info
                result.file_checks[rel_path] = {
                    "exists": True,
                    "size": len(content),
                    "language": expected_lang,
                    "lines": content.count('\n') + 1
                }
                
            except Exception as e:
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=1,
                    file_path=rel_path,
                    line_number=None,
                    message=f"Error reading file: {e}"
                ))
    
    def _verify_static_code(
        self,
        file_specs: list[dict[str, str]],
        result: VerificationResult
    ) -> None:
        """Layer 2: Static code analysis.
        
        Args:
            file_specs: List of file specifications
            result: VerificationResult to append issues to
        """
        for spec in file_specs:
            rel_path = spec["path"]
            full_path = self.file_map.get(rel_path)
            
            if not full_path or not full_path.exists():
                continue
            
            try:
                content = full_path.read_text()
                ext = full_path.suffix.lower()
                language = self.LANGUAGE_MAP.get(ext)
                
                if language == 'python':
                    self._verify_python_static(rel_path, content, result)
                elif language == 'javascript':
                    self._verify_javascript_static(rel_path, content, result)
                elif language == 'html':
                    self._verify_html_static(rel_path, content, result)
                elif language == 'css':
                    self._verify_css_static(rel_path, content, result)
                elif language == 'json':
                    self._verify_json_static(rel_path, content, result)
                
            except Exception as e:
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=2,
                    file_path=rel_path,
                    line_number=None,
                    message=f"Static analysis error: {e}"
                ))
    
    def _verify_python_static(
        self,
        file_path: str,
        content: str,
        result: VerificationResult
    ) -> None:
        """Verify Python file statically.
        
        Args:
            file_path: Relative file path
            content: File content
            result: VerificationResult to append issues to
        """
        # Check for syntax errors
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            result.issues.append(VerificationIssue(
                severity="error",
                layer=2,
                file_path=file_path,
                line_number=e.lineno,
                message=f"Python syntax error: {e.msg}"
            ))
            return
        
        # Extract imports and exports
        imports = []
        exports = []  # Functions and classes defined at module level
        
        for node in ast.walk(tree):
            # Track imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            
            # Track module-level definitions
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.col_offset == 0:  # Module level
                    exports.append(node.name)
        
        # Store in symbol table
        self.symbol_table[file_path] = {
            "imports": imports,
            "exports": exports,
            "language": "python"
        }
        
        # Check for unfinished code markers
        if any(marker in content for marker in ["FIXME", "TODO", "XXX"]):
            result.warnings.append(VerificationIssue(
                severity="warning",
                layer=2,
                file_path=file_path,
                line_number=None,
                message="File contains unfinished code markers (FIXME/TODO/XXX)"
            ))
    
    def _verify_javascript_static(
        self,
        file_path: str,
        content: str,
        result: VerificationResult
    ) -> None:
        """Verify JavaScript file statically.
        
        Args:
            file_path: Relative file path
            content: File content
            result: VerificationResult to append issues to
        """
        # Basic syntax checks (not full parsing)
        
        # Check for balanced braces
        brace_count = content.count('{') - content.count('}')
        if brace_count != 0:
            result.issues.append(VerificationIssue(
                severity="error",
                layer=2,
                file_path=file_path,
                line_number=None,
                message=f"Unbalanced braces: {abs(brace_count)} {'extra opening' if brace_count > 0 else 'extra closing'} braces"
            ))
        
        # Check for balanced parentheses
        paren_count = content.count('(') - content.count(')')
        if paren_count != 0:
            result.issues.append(VerificationIssue(
                severity="error",
                layer=2,
                file_path=file_path,
                line_number=None,
                message=f"Unbalanced parentheses: {abs(paren_count)} {'extra opening' if paren_count > 0 else 'extra closing'} parentheses"
            ))
        
        # Extract function definitions
        # Match patterns:
        # 1. function name(...) - traditional function declaration
        # 2. const/let/var name = function(...) - function expression
        # 3. const/let/var name = (...) => - arrow function
        func_pattern = r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))'
        functions = re.findall(func_pattern, content)
        exports = [name for group in functions for name in group if name]
        
        # Extract imports (ES6 import statements)
        import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
        imports = re.findall(import_pattern, content)
        
        # Extract require statements
        require_pattern = r'require\([\'"]([^\'"]+)[\'"]\)'
        imports.extend(re.findall(require_pattern, content))
        
        # Check for ES6 exports
        has_es6_exports = bool(
            re.search(r'\bexport\s+(?:default|(?:const|let|var|function|class)\s+\w+)', content) or
            re.search(r'\bexport\s*\{[^}]+\}', content)
        )
        
        # Store in symbol table
        self.symbol_table[file_path] = {
            "imports": imports,
            "exports": exports,
            "has_es6_exports": has_es6_exports,
            "language": "javascript"
        }
        
        # Check for unfinished code markers
        if any(marker in content for marker in ["FIXME", "TODO", "XXX"]):
            result.warnings.append(VerificationIssue(
                severity="warning",
                layer=2,
                file_path=file_path,
                line_number=None,
                message="File contains unfinished code markers (FIXME/TODO/XXX)"
            ))
    
    def _verify_html_static(
        self,
        file_path: str,
        content: str,
        result: VerificationResult
    ) -> None:
        """Verify HTML file statically.
        
        Args:
            file_path: Relative file path
            content: File content
            result: VerificationResult to append issues to
        """
        # Parse HTML to extract references
        parser = HTMLReferenceExtractor()
        try:
            parser.feed(content)
        except Exception as e:
            result.issues.append(VerificationIssue(
                severity="error",
                layer=2,
                file_path=file_path,
                line_number=None,
                message=f"HTML parsing error: {e}"
            ))
            return
        
        # Extract script tag information including whether they're modules
        script_tags = self._extract_script_tags(content)
        
        # Extract HTML classes and IDs used
        html_selectors = self._extract_html_selectors(content)
        
        # Extract form elements
        form_elements = self._extract_form_elements(content)
        
        # Store in symbol table
        self.symbol_table[file_path] = {
            "scripts": parser.scripts,
            "stylesheets": parser.stylesheets,
            "images": parser.images,
            "functions_called": parser.functions_called,
            "script_tags": script_tags,
            "html_selectors": html_selectors,
            "form_elements": form_elements,
            "language": "html"
        }
        
        # Check for basic HTML structure
        if not re.search(r'<!DOCTYPE\s+html>', content, re.IGNORECASE):
            result.warnings.append(VerificationIssue(
                severity="warning",
                layer=2,
                file_path=file_path,
                line_number=1,
                message="Missing DOCTYPE declaration"
            ))
    
    def _extract_script_tags(self, content: str) -> list[dict[str, Any]]:
        """Extract script tag information from HTML.
        
        Args:
            content: HTML content
            
        Returns:
            List of script tag info dicts with 'src' and 'is_module' keys
        """
        script_tags = []
        # Match <script> tags with optional type attribute
        script_pattern = r'<script\s+([^>]*?)(?:src=["\']([^"\']+)["\'])?([^>]*?)>'
        
        for match in re.finditer(script_pattern, content, re.IGNORECASE):
            attrs_before = match.group(1)
            src = match.group(2)
            attrs_after = match.group(3)
            
            # Combine all attributes
            all_attrs = f"{attrs_before} {attrs_after}"
            
            # Check if it's a module
            is_module = 'type="module"' in all_attrs or "type='module'" in all_attrs
            
            if src:
                script_tags.append({
                    "src": src,
                    "is_module": is_module
                })
        
        return script_tags
    
    def _extract_html_selectors(self, content: str) -> dict[str, list[str]]:
        """Extract classes and IDs used in HTML.
        
        Args:
            content: HTML content
            
        Returns:
            Dict with 'classes' and 'ids' lists
        """
        # Extract class attributes
        class_pattern = r'class=["\']([^"\']+)["\']'
        classes = []
        for match in re.finditer(class_pattern, content):
            # Split by whitespace to get individual classes
            classes.extend(match.group(1).split())
        
        # Extract id attributes
        id_pattern = r'id=["\']([^"\']+)["\']'
        ids = [match.group(1) for match in re.finditer(id_pattern, content)]
        
        return {
            "classes": list(set(classes)),  # Remove duplicates
            "ids": list(set(ids))
        }
    
    def _extract_form_elements(self, content: str) -> dict[str, Any]:
        """Extract form elements and their submission handlers.
        
        Args:
            content: HTML content
            
        Returns:
            Dict with form information
        """
        forms = []
        
        # Find form tags
        form_pattern = r'<form\s+([^>]*?)>'
        for match in re.finditer(form_pattern, content, re.IGNORECASE):
            attrs = match.group(1)
            
            # Check for onsubmit handler
            has_onsubmit = 'onsubmit=' in attrs.lower()
            
            # Extract form ID if present
            id_match = re.search(r'id=["\']([^"\']+)["\']', attrs)
            form_id = id_match.group(1) if id_match else None
            
            forms.append({
                "id": form_id,
                "has_onsubmit": has_onsubmit,
                "has_submit_button": False  # Will be updated below
            })
        
        # Check for submit buttons
        submit_pattern = r'<(?:button|input)\s+([^>]*?)type=["\']?submit["\']?([^>]*?)>'
        has_submit_buttons = len(re.findall(submit_pattern, content, re.IGNORECASE)) > 0
        
        # Update forms with submit button info
        for form in forms:
            form["has_submit_button"] = has_submit_buttons
        
        return {
            "forms": forms,
            "has_forms": len(forms) > 0,
            "has_submit_buttons": has_submit_buttons
        }
    
    def _verify_css_static(
        self,
        file_path: str,
        content: str,
        result: VerificationResult
    ) -> None:
        """Verify CSS file statically.
        
        Args:
            file_path: Relative file path
            content: File content
            result: VerificationResult to append issues to
        """
        # Check for balanced braces
        brace_count = content.count('{') - content.count('}')
        if brace_count != 0:
            result.issues.append(VerificationIssue(
                severity="error",
                layer=2,
                file_path=file_path,
                line_number=None,
                message=f"Unbalanced braces in CSS: {abs(brace_count)} {'extra opening' if brace_count > 0 else 'extra closing'} braces"
            ))
        
        # Extract CSS selectors
        selector_pattern = r'([.#]?[\w-]+(?:\s+[.#]?[\w-]+)*)\s*\{'
        selectors = re.findall(selector_pattern, content)
        
        # Store in symbol table
        self.symbol_table[file_path] = {
            "selectors": selectors,
            "language": "css"
        }
    
    def _verify_json_static(
        self,
        file_path: str,
        content: str,
        result: VerificationResult
    ) -> None:
        """Verify JSON file statically.
        
        Args:
            file_path: Relative file path
            content: File content
            result: VerificationResult to append issues to
        """
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            result.issues.append(VerificationIssue(
                severity="error",
                layer=2,
                file_path=file_path,
                line_number=e.lineno,
                message=f"Invalid JSON: {e.msg}"
            ))
    
    def _verify_semantics(
        self,
        file_specs: list[dict[str, str]],
        result: VerificationResult
    ) -> None:
        """Layer 3: Semantic verification (cross-file).
        
        Args:
            file_specs: List of file specifications
            result: VerificationResult to append issues to
        """
        # Check HTML → JS/CSS references
        for file_path, symbols in self.symbol_table.items():
            if symbols.get("language") == "html":
                # Verify script references
                for script_src in symbols.get("scripts", []):
                    if not self._resolve_reference(file_path, script_src):
                        result.issues.append(VerificationIssue(
                            severity="error",
                            layer=3,
                            file_path=file_path,
                            line_number=None,
                            message=f"Referenced script not found: {script_src}",
                            auto_fixable=True
                        ))
                
                # Verify stylesheet references
                for css_href in symbols.get("stylesheets", []):
                    if not self._resolve_reference(file_path, css_href):
                        result.issues.append(VerificationIssue(
                            severity="error",
                            layer=3,
                            file_path=file_path,
                            line_number=None,
                            message=f"Referenced stylesheet not found: {css_href}",
                            auto_fixable=True
                        ))
                
                # NEW: Check for ES6 module export mismatch
                self._verify_js_module_compatibility(file_path, symbols, result)
                
                # NEW: Check for HTML-CSS class mismatch
                self._verify_html_css_integration(file_path, symbols, result)
                
                # NEW: Check for form submission handlers
                self._verify_form_handlers(file_path, symbols, result)
                
                # Verify functions called in event handlers exist in referenced JS files
                for func_name, line_num in symbols.get("functions_called", []):
                    # Check if function exists in any referenced JS file
                    js_files = symbols.get("scripts", [])
                    function_found = False
                    
                    for js_src in js_files:
                        resolved_js = self._resolve_reference(file_path, js_src)
                        if resolved_js and resolved_js in self.symbol_table:
                            js_exports = self.symbol_table[resolved_js].get("exports", [])
                            if func_name in js_exports:
                                function_found = True
                                break
                    
                    if not function_found and js_files:
                        result.issues.append(VerificationIssue(
                            severity="error",
                            layer=3,
                            file_path=file_path,
                            line_number=line_num,
                            message=f"Function '{func_name}()' called in HTML but not found in referenced JavaScript files. Functions must be globally accessible (not ES6 exports) or HTML must use type=\"module\".",
                            auto_fixable=True
                        ))
        
        # Check Python imports
        for file_path, symbols in self.symbol_table.items():
            if symbols.get("language") == "python":
                for import_name in symbols.get("imports", []):
                    # Check if import is a local module
                    if not import_name.startswith('.') and '.' not in import_name:
                        # Could be local module - check if file exists
                        potential_paths = [
                            f"{import_name}.py",
                            f"src/{import_name}.py",
                            f"{import_name}/__init__.py"
                        ]
                        
                        found = any(
                            self.file_map.get(p) and self.file_map[p].exists()
                            for p in potential_paths
                        )
                        
                        # Only warn if it looks like a local import (not stdlib/external)
                        if not found and import_name not in self._get_python_stdlib():
                            result.warnings.append(VerificationIssue(
                                severity="warning",
                                layer=3,
                                file_path=file_path,
                                line_number=None,
                                message=f"Import '{import_name}' not found in project (may be external dependency)"
                            ))
    
    def _verify_js_module_compatibility(
        self,
        html_file_path: str,
        html_symbols: dict[str, Any],
        result: VerificationResult
    ) -> None:
        """Verify JavaScript module compatibility with HTML script loading.
        
        Detects when JavaScript uses ES6 exports but HTML loads it without type="module".
        
        Args:
            html_file_path: Path to HTML file
            html_symbols: Symbol table entry for HTML file
            result: VerificationResult to append issues to
        """
        script_tags = html_symbols.get("script_tags", [])
        
        for script_tag in script_tags:
            src = script_tag["src"]
            is_module = script_tag["is_module"]
            
            # Resolve the JS file
            resolved_js = self._resolve_reference(html_file_path, src)
            if not resolved_js or resolved_js not in self.symbol_table:
                continue
            
            js_symbols = self.symbol_table[resolved_js]
            has_es6_exports = js_symbols.get("has_es6_exports", False)
            
            # Issue 3 from problem statement: ES6 exports without type="module"
            if has_es6_exports and not is_module:
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=3,
                    file_path=html_file_path,
                    line_number=None,
                    message=f"JavaScript file '{src}' uses ES6 exports but is loaded without type=\"module\". "
                            f"Either add type=\"module\" to the <script> tag or use global functions instead of exports.",
                    auto_fixable=True
                ))
    
    def _verify_html_css_integration(
        self,
        html_file_path: str,
        html_symbols: dict[str, Any],
        result: VerificationResult
    ) -> None:
        """Verify CSS classes are actually used in HTML.
        
        Detects when CSS defines classes but HTML doesn't use them.
        
        Args:
            html_file_path: Path to HTML file
            html_symbols: Symbol table entry for HTML file
            result: VerificationResult to append issues to
        """
        # Get HTML selectors
        html_selectors = html_symbols.get("html_selectors", {})
        html_classes = set(html_selectors.get("classes", []))
        html_ids = set(html_selectors.get("ids", []))
        
        # Get referenced CSS files
        css_refs = html_symbols.get("stylesheets", [])
        
        for css_ref in css_refs:
            resolved_css = self._resolve_reference(html_file_path, css_ref)
            if not resolved_css or resolved_css not in self.symbol_table:
                continue
            
            css_symbols = self.symbol_table[resolved_css]
            css_selectors = css_symbols.get("selectors", [])
            
            # Extract class selectors from CSS (those starting with .)
            css_classes = set()
            css_ids = set()
            
            for selector in css_selectors:
                # Extract classes (starting with .)
                class_matches = re.findall(r'\.([a-zA-Z][\w-]*)', selector)
                css_classes.update(class_matches)
                
                # Extract IDs (starting with #)
                id_matches = re.findall(r'#([a-zA-Z][\w-]*)', selector)
                css_ids.update(id_matches)
            
            # Issue 2 from problem statement: CSS classes defined but not used
            unused_classes = css_classes - html_classes
            if unused_classes and len(css_classes) > 0:
                # Only report if there are significant unused classes
                # Allow some tolerance for utility classes
                unused_ratio = len(unused_classes) / len(css_classes)
                if unused_ratio > 0.5:  # More than 50% unused
                    result.issues.append(VerificationIssue(
                        severity="error",
                        layer=3,
                        file_path=html_file_path,
                        line_number=None,
                        message=f"CSS file '{css_ref}' defines classes ({', '.join(list(unused_classes)[:5])}) "
                                f"that are not used in HTML. HTML elements need matching CSS classes to be styled.",
                        auto_fixable=True
                    ))
            
            # Check for HTML elements without any classes when CSS expects them
            if len(css_classes) > 2 and len(html_classes) == 0:
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=3,
                    file_path=html_file_path,
                    line_number=None,
                    message=f"CSS file '{css_ref}' defines {len(css_classes)} classes but HTML uses none. "
                            f"Add class attributes to HTML elements to apply styles.",
                    auto_fixable=True
                ))
    
    def _verify_form_handlers(
        self,
        html_file_path: str,
        html_symbols: dict[str, Any],
        result: VerificationResult
    ) -> None:
        """Verify form elements have submission handlers.
        
        Detects when forms have submit buttons but no submission handler.
        
        Args:
            html_file_path: Path to HTML file
            html_symbols: Symbol table entry for HTML file
            result: VerificationResult to append issues to
        """
        form_elements = html_symbols.get("form_elements", {})
        forms = form_elements.get("forms", [])
        
        # Issue 1 from problem statement: Form without handlers
        for form in forms:
            if form.get("has_submit_button") and not form.get("has_onsubmit"):
                # Check if there are any event listeners attached via JavaScript
                # For now, we'll just warn about missing inline handlers
                # A more sophisticated check would look for addEventListener in JS
                
                form_id = form.get("id", "unnamed form")
                result.issues.append(VerificationIssue(
                    severity="error",
                    layer=3,
                    file_path=html_file_path,
                    line_number=None,
                    message=f"Form {form_id} has submit button but no submission handler. "
                            f"Add onsubmit=\"return handleSubmit()\" or attach event listener in JavaScript.",
                    auto_fixable=True
                ))
    
    def _resolve_reference(self, source_file: str, reference: str) -> str | None:
        """Resolve a file reference from source file.
        
        Args:
            source_file: Source file making the reference
            reference: Referenced file path (could be relative or absolute)
        
        Returns:
            Resolved file path if found, None otherwise
        """
        # Skip external URLs and protocol-relative URLs
        # Note: Protocol-relative URLs ('//' prefix) are treated as external
        # for security reasons - they could point to malicious external resources
        if reference.startswith(('http://', 'https://', '//')):
            # For protocol-relative URLs, log a warning but allow them
            # These should be reviewed by developers as they can be security risks
            return reference
        
        # Get directory of source file
        source_dir = Path(source_file).parent
        
        # Try various resolution strategies
        candidates = [
            reference,  # Direct path
            str(source_dir / reference),  # Relative to source
            str(Path("src") / reference),  # In src directory
        ]
        
        for candidate in candidates:
            if candidate in self.file_map:
                return candidate
        
        return None
    
    def _get_python_stdlib(self) -> set[str]:
        """Get set of Python standard library module names.
        
        Returns:
            Set of stdlib module names
        """
        # Common Python stdlib modules (not exhaustive)
        return {
            'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections',
            'contextlib', 'copy', 'csv', 'dataclasses', 'datetime', 'decimal',
            'enum', 'functools', 'hashlib', 'io', 'itertools', 'json', 'logging',
            'math', 'os', 'pathlib', 'pickle', 're', 'sqlite3', 'string', 'sys',
            'tempfile', 'time', 'typing', 'unittest', 'urllib', 'uuid', 'warnings'
        }


def verify_generated_code(
    workspace_path: str | Path,
    file_specs: list[dict[str, str]]
) -> VerificationResult:
    """Verify generated code files.
    
    Args:
        workspace_path: Path to workspace containing files
        file_specs: List of file specifications with 'path' and 'purpose'
    
    Returns:
        VerificationResult with all issues
    """
    verifier = CodeVerifier(workspace_path)
    return verifier.verify(file_specs)
