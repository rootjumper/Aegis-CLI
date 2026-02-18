# Code Verification Strategy

**Date**: 2026-02-18  
**Status**: ✅ Implemented  
**Version**: 1.0

## Overview

The Code Verification Strategy is a 4-layer validation system that ensures generated code actually works before returning it to users. This eliminates common issues like missing imports, broken file references, and syntax errors.

## Problem Solved

### Before Verification
```
User Request → Orchestrator Plans → CoderAgent Generates → Files Written → Task: SUCCESS
                                                                              ❌ User: Code Doesn't Work
```

**Common Issues:**
- Cross-file reference mismatches (File A imports File B, but File B not found)
- Import paths broken (code imports from locations that don't exist)
- Export/visibility mismatch (function defined but not exported)
- Symbol name mismatches (File A calls `calculateResult()` but File B exports `calculate()`)
- Syntax errors in generated files
- Missing dependencies

### After Verification
```
User Request → Orchestrator Plans → CoderAgent Generates → Files Written → 
  → Verification (Layers 1-3) → Auto-Fix Issues → Re-verify → Task: SUCCESS ✅
                                                              User: Code Works! 🎉
```

## Architecture

### 4-Layer Verification Approach

#### **Layer 1: File Structure Verification**
**Verifies:**
- All planned files exist and have content
- File extensions match declared types
- Files contain expected language signatures
- No duplicate files or naming conflicts

**Catches:**
- Missing files
- Truncated files
- Wrong file types
- Empty files

#### **Layer 2: Static Code Analysis**
**Verifies:**
- Valid syntax (bracket matching, parseable code)
- All imports reference existing files
- All external dependencies listed
- No circular imports
- Unfinished code markers (FIXME/TODO/XXX)

**Catches:**
- Syntax errors
- Broken imports
- Missing dependencies
- Incomplete code

**Supported Languages:**
- Python (AST parsing)
- JavaScript/TypeScript (regex-based)
- HTML (HTML parser)
- CSS (brace matching)
- JSON (JSON validation)

#### **Layer 3: Semantic Verification (Cross-File Integration)**
**Verifies:**
- All imports are satisfiable (imported files exist and export needed symbols)
- No circular dependencies
- Function/method signatures match between definition and calls
- Type consistency (where available)
- All required files in plan OR marked as external dependencies

**Catches:**
- Export mismatches
- Function reference failures
- Circular dependencies
- Type conflicts

**Examples:**
```html
<!-- HTML references script.js -->
<script src="script.js"></script>
✅ Verified: script.js exists in file list

<!-- HTML calls function in event handler -->
<button onclick="calculate()">Click</button>
✅ Verified: calculate() exists in referenced JS files
```

#### **Layer 4: Runtime Verification (Optional)**
*Not yet implemented - reserved for future enhancements*

**Potential Features:**
- For web projects: Test in headless browser (JSDOM/Puppeteer)
- For Python: Import and test modules
- Runtime execution tests

## Implementation

### Core Module: `aegis/core/code_verifier.py`

**Key Classes:**

1. **`VerificationIssue`** - Represents a single issue
   ```python
   @dataclass
   class VerificationIssue:
       severity: str  # "error", "warning", "info"
       layer: int  # 1, 2, 3, or 4
       file_path: str
       line_number: int | None
       message: str
       auto_fixable: bool = False
   ```

2. **`VerificationResult`** - Contains all verification results
   ```python
   @dataclass
   class VerificationResult:
       passed: bool
       issues: list[VerificationIssue]
       warnings: list[VerificationIssue]
       file_checks: dict[str, dict[str, Any]]
       
       @property
       def critical_errors(self) -> list[VerificationIssue]
       
       @property
       def auto_fixable_errors(self) -> list[VerificationIssue]
       
       def get_summary(self) -> str
   ```

3. **`CodeVerifier`** - Main verification engine
   ```python
   class CodeVerifier:
       def __init__(self, workspace_path: str | Path)
       def verify(self, file_specs: list[dict[str, str]]) -> VerificationResult
   ```

### Integration with Orchestrator

The verification phase is integrated into the orchestrator's `process()` method as **Phase 4**:

```python
# PHASE 4: VERIFICATION with iteration (max 3 attempts)
max_verification_attempts = 3

for attempt in range(max_verification_attempts):
    # Run verification
    verification_result = verify_generated_code(workspace_path, file_specs)
    
    # If verification passed, break
    if verification_result.passed:
        break
    
    # Try to fix issues (if not last attempt)
    if attempt < max_verification_attempts - 1:
        fixed = await self._attempt_fix_verification_issues(...)
        if not fixed:
            break
```

### Auto-Fix Strategy

When verification fails, the system attempts to fix issues:

1. **Group errors by file** - Organize issues by which file has the problem
2. **Regenerate problematic files** - Pass error messages to CoderAgent with context:
   ```
   FIX THESE VERIFICATION ERRORS:
     - Referenced script not found: script.js
     - Function 'calculateResult()' called but not found
   ```
3. **Re-verify** - Run verification again on the regenerated files
4. **Iterate** - Repeat up to 3 times total

## Verification Report Format

### Success Example
```
✅ PASSED
Critical Errors: 0
Warnings: 1

=== Warnings ===
⚠️ WARNING: index.html: Class selector '.advanced' never used in HTML
```

### Failure Example
```
❌ FAILED
Critical Errors: 2
Warnings: 1

=== Critical Errors ===
❌ ERROR: index.html: Referenced script not found: script.js
❌ ERROR: calculator.js: Unbalanced braces: 1 extra opening braces

=== Warnings ===
⚠️ WARNING: styles.css: Selector '#calculator' never used in HTML
```

## API Usage

### Standalone Usage
```python
from aegis.core.code_verifier import verify_generated_code

# Verify generated files
result = verify_generated_code(
    workspace_path="/path/to/workspace",
    file_specs=[
        {"path": "index.html", "purpose": "Main page"},
        {"path": "app.js", "purpose": "Application logic"}
    ]
)

if result.passed:
    print("✅ All checks passed!")
else:
    print(result.get_summary())
    for error in result.critical_errors:
        print(f"  {error}")
```

### Orchestrator Integration
The verification is **automatic** when using the orchestrator:

```python
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.base import AgentTask

orchestrator = OrchestratorAgent()

task = AgentTask(
    id="generate_app",
    type="code",
    payload={
        "description": "Create a calculator web app"
    }
)

response = await orchestrator.process(task)

# Response includes verification info
if response.status == "SUCCESS":
    verification = response.data["verification"]
    print(f"Passed: {verification['passed']}")
    print(f"Warnings: {verification['warnings']}")
    print(verification['summary'])
```

## Testing

### Test Coverage

**Verifier Tests** (`tests/test_code_verifier.py`): 20 tests
- Layer 1 tests: File structure validation
- Layer 2 tests: Static analysis (Python, JavaScript, HTML, CSS, JSON)
- Layer 3 tests: Semantic verification (cross-file references)
- Complete workflow tests

**Integration Tests** (`tests/test_verification_integration.py`): 5 tests
- Orchestrator integration
- Iteration mechanism
- Verification reporting

**All tests passing**: ✅ 24/25 (1 skipped - needs LLM provider)

### Running Tests
```bash
# Run verifier tests
pytest tests/test_code_verifier.py -v

# Run integration tests
pytest tests/test_verification_integration.py -v

# Run all tests
pytest tests/ -v
```

## Benefits

### ✅ What Verification Solves

1. **Catches mismatches** between files before returning to user
2. **Provides actionable errors** instead of silent failures
3. **Enables iteration** - can fix and regenerate automatically
4. **Improves success rate** - most generated code now works
5. **Builds trust** - "this was verified to work"

### ❌ Limitations

1. **Doesn't solve**: Complex logic bugs (those are design issues)
2. **Limited by**: LLM generation quality (can't always fix)
3. **Best for**: Mechanical issues (80% of common problems)
   - Missing files
   - Wrong paths
   - Export/import issues
   - Syntax errors
   - Reference mismatches

## Configuration

### Maximum Verification Attempts
Hardcoded to 3 in `orchestrator.py`:
```python
max_verification_attempts = 3
```

### Supported Languages
Defined in `CodeVerifier.LANGUAGE_MAP`:
```python
LANGUAGE_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.html': 'html',
    '.css': 'css',
    '.json': 'json',
    # ... and more
}
```

## Future Enhancements

### Layer 4: Runtime Verification
- Execute Python imports to catch runtime errors
- Run JavaScript in headless browser
- Execute tests automatically
- Validate API endpoints

### Enhanced Auto-Fix
- Path correction (e.g., `script.js` → `js/script.js`)
- Function export detection and auto-wrapping
- Import statement generation
- Dependency installation suggestions

### Language Support
- Add TypeScript type checking
- Add Rust borrow checker integration
- Add Go module resolution
- Add Java classpath verification

## Metrics

- **Code**: 750+ lines in `code_verifier.py`
- **Tests**: 600+ lines across 25 tests
- **Coverage**: Layers 1-3 fully implemented
- **Languages**: 12+ file types supported
- **Integration**: Seamless with orchestrator

## See Also

- [Problem Statement](../README.md) - Original requirements
- [Code Verifier Source](../aegis/core/code_verifier.py)
- [Orchestrator Integration](../aegis/agents/orchestrator.py)
- [Test Suite](../tests/test_code_verifier.py)
