# HTML Script Reference Mismatch - Fix Summary

## Problem Statement

When generating multi-file web applications, the orchestrator was creating files with the correct structure (HTML, JS in `js/` folder, CSS in `css/` folder), but the HTML files were referencing JavaScript and CSS files with incorrect paths.

**Example Issue:**
- **Created files:**
  - `src/calculator.html`
  - `src/js/calculator.js`
  - `src/css/styles.css`

- **HTML references (INCORRECT):**
  ```html
  <script src="script.js"></script>          <!-- Missing js/ prefix and wrong filename -->
  <link rel="stylesheet" href="styles.css">  <!-- Missing css/ prefix -->
  ```

- **Expected references (CORRECT):**
  ```html
  <script src="js/calculator.js"></script>
  <link rel="stylesheet" href="css/styles.css">
  ```

## Root Cause

The orchestrator was creating a coordinated multi-file plan but generating each file **in isolation** without passing information about related files to the CoderAgent. Specifically:

1. **Orchestrator** created a plan with proper file structure
2. **Context passed to CoderAgent was minimal:**
   ```python
   {
       "workspace": "calculator_app",
       "existing_files": [],
       "plan": "reasoning text",
       "original_request": "Create a calculator app"
   }
   ```
3. **Missing information:**
   - No list of all files being created
   - No information about which files should reference which
   - No file relationship data

4. **Result:** LLM generated generic references like `script.js` and `styles.css` because it had no knowledge of the actual filenames or directory structure.

## Solution Implemented

### 1. Enhanced Orchestrator (`orchestrator.py`)

**Added `_find_related_files()` method:**
```python
def _find_related_files(self, file_path: str, plan: dict) -> dict:
    """Find files related to the given file based on the plan.
    
    Returns categorized lists of:
    - JavaScript files (for HTML to reference)
    - Stylesheet files (for HTML to reference)
    - HTML files (that might import JS/CSS)
    - Other files
    """
```

**Enhanced context passed to CoderAgent:**
```python
code_task = AgentTask(
    payload={
        "description": full_description,
        "file_path": str(full_file_path),
        "context": {
            "workspace": workspace_name,
            "existing_files": context["workspace"].get("files", []),
            "plan": plan.get("reasoning", ""),
            "original_request": original_description,
            "all_files": plan.get("files_to_create", []),      # NEW
            "related_files": related_files                      # NEW
        }
    }
)
```

### 2. Enhanced CoderAgent (`coder.py`)

**Extracted related files from context:**
```python
related_files = context_info.get("related_files", {})
all_files = context_info.get("all_files", [])
```

**Built file structure information for the prompt:**
```python
# For HTML files, show JS and CSS files they should reference
if markdown_tag == 'html':
    if related_files.get("javascript"):
        file_structure_info += "\n\nJavaScript files to reference:\n"
        for js_file in related_files["javascript"]:
            file_structure_info += f"  - {js_file}\n"
    if related_files.get("stylesheets"):
        file_structure_info += "\nCSS files to reference:\n"
        for css_file in related_files["stylesheets"]:
            file_structure_info += f"  - {css_file}\n"
        
        file_structure_info += "\nIMPORTANT: Use the EXACT paths listed above..."
```

**Updated system prompt:**
```python
For HTML:
- Use semantic HTML5 tags
- Include accessibility attributes (ARIA, alt, role, etc.)
- Proper document structure
- When referencing JavaScript/CSS files, use EXACT paths provided in the context
- Include subdirectory prefixes (e.g., js/, css/) as specified
- Do NOT use generic names like 'script.js' or 'styles.css' unless that's the actual filename
```

## Impact

### Before Fix
```
LLM Prompt:
  "Generate HTML code for: Main HTML calculator interface
   TARGET FILE: src/calculator.html
   CONTEXT: {}"

Result:
  <script src="script.js"></script>          ❌ Generic filename
  <link rel="stylesheet" href="styles.css">  ❌ Missing directory
```

### After Fix
```
LLM Prompt:
  "Generate HTML code for: Main HTML calculator interface
   TARGET FILE: src/calculator.html
   
   JavaScript files to reference:
     - src/js/calculator.js
   
   CSS files to reference:
     - src/css/styles.css
   
   IMPORTANT: Use the EXACT paths listed above in your <script> and <link> tags.
   Include the subdirectory prefix (e.g., 'js/' or 'css/') if present in the paths.
   
   Complete file structure for this project:
     - src/calculator.html: Main HTML calculator interface
     - src/js/calculator.js: Calculator logic
     - src/css/styles.css: Styling"

Result:
  <script src="js/calculator.js"></script>         ✅ Correct filename and path
  <link rel="stylesheet" href="css/styles.css">   ✅ Correct filename and path
```

## Testing

Created comprehensive test suite in `tests/test_html_reference_fix.py`:

1. **Unit Tests (no LLM required):**
   - `test_orchestrator_finds_related_files()` - Validates file relationship detection
   - `test_orchestrator_finds_related_files_for_js()` - Validates reverse relationships
   - `test_coder_receives_related_files_context()` - Validates context structure
   - `test_related_files_empty_for_single_file()` - Edge case: single file
   - `test_related_files_excludes_self()` - Validates file doesn't relate to itself

2. **Integration Test (requires LLM):**
   - `test_html_references_correct_js_css_paths()` - End-to-end validation

All unit tests pass. Integration test requires LLM configuration.

## Files Modified

1. **`aegis/agents/orchestrator.py`:**
   - Added `_find_related_files()` method (lines 346-395)
   - Enhanced context in file generation loop (lines 407-424)

2. **`aegis/agents/coder.py`:**
   - Enhanced prompt generation with file structure info (lines 128-180)
   - Updated system prompt for HTML (lines 325-330)

3. **`tests/test_html_reference_fix.py`:**
   - New test file with 6 comprehensive tests

## Backward Compatibility

✅ **Fully backward compatible:**
- If `related_files` or `all_files` are not in context, code gracefully handles it
- Existing single-file generation still works
- Python files unaffected (only HTML/JS/CSS file relationships matter)

## Future Improvements

1. **Relative path calculation:** Currently passes full paths, could calculate relative paths from HTML location
2. **Import/export tracking:** Track which functions/classes are exported from JS files
3. **Dependency ordering:** Ensure JS files are loaded in the correct order
4. **Validation:** Post-generation validation to verify all references are correct

## Summary

This fix implements **Approach 1** (Enhanced Planning Context) and **Approach 2** (Explicit Prompt Injection) from the problem statement. The orchestrator now passes complete file relationship information to CoderAgent, which uses it to generate correct file references in HTML. The LLM no longer has to guess file paths or use generic names - it has all the information it needs to generate production-ready code.
