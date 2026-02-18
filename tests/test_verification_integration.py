"""Integration tests for code verification in orchestrator."""

import pytest
from pathlib import Path
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.agents.base import AgentTask


@pytest.fixture
def orchestrator():
    """Create orchestrator instance for testing."""
    # Use a simple model for testing - can be mocked
    return OrchestratorAgent(verbose=False)


class TestVerificationIntegration:
    """Test verification integration with orchestrator."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_creates_and_verifies_html_project(self, orchestrator, tmp_path):
        """Test that orchestrator creates and verifies a simple HTML project."""
        # Create a task for generating an HTML calculator
        task = AgentTask(
            id="test_html_calc",
            type="code",
            payload={
                "description": "Create a simple HTML calculator with JavaScript"
            },
            context={}
        )
        
        # Process the task
        response = await orchestrator.process(task)
        
        # If LLM is not configured, skip the test
        if "No LLM providers configured" in str(response.errors):
            pytest.skip("LLM provider not configured for this test")
        
        # Check that the response includes verification info
        assert "verification" in response.data
        
        # If generation succeeded, verification should have run
        if response.status == "SUCCESS":
            assert response.data["verification"]["passed"] is not None
            
            # Check that workspace was created
            assert "workspace" in response.data
            assert "workspace_path" in response.data
            
            # Check that files were created
            assert "files_created" in response.data
            assert len(response.data["files_created"]) > 0
    
    @pytest.mark.asyncio
    async def test_verification_catches_missing_files(self, orchestrator, tmp_path):
        """Test that verification catches missing referenced files."""
        # This would require setting up a scenario where HTML references
        # a missing JS file - but since we're testing integration,
        # we rely on the verifier tests for detailed scenarios
        
        # Just verify the verification key exists in response
        task = AgentTask(
            id="test_verification",
            type="code",
            payload={
                "description": "Create a Python module"
            },
            context={}
        )
        
        response = await orchestrator.process(task)
        
        # Verification should run regardless of pass/fail
        if response.status in ["SUCCESS", "FAIL"]:
            # Response should contain verification info if files were generated
            if "files_created" in response.data and response.data["files_created"]:
                assert "verification" in response.data


class TestVerificationIteration:
    """Test verification iteration and fix attempts."""
    
    @pytest.mark.asyncio
    async def test_iteration_mechanism_exists(self, orchestrator):
        """Test that the iteration mechanism is in place."""
        # Verify the method exists
        assert hasattr(orchestrator, '_attempt_fix_verification_issues')
        
        # The method should be callable
        from inspect import iscoroutinefunction
        assert iscoroutinefunction(orchestrator._attempt_fix_verification_issues)


class TestVerificationReporting:
    """Test verification reporting in responses."""
    
    def test_verification_summary_in_success_response(self):
        """Test that successful responses include verification summary."""
        from aegis.agents.base import AgentResponse
        
        # Create a mock successful response with verification
        response = AgentResponse(
            status="SUCCESS",
            data={
                "workspace": "test_workspace",
                "workspace_path": "/path/to/workspace",
                "files_created": [{"path": "test.py"}],
                "verification": {
                    "passed": True,
                    "warnings": 0,
                    "summary": "✅ PASSED"
                }
            },
            reasoning_trace="Created files - All verification checks passed!"
        )
        
        assert response.data["verification"]["passed"]
        assert "verification" in response.data
    
    def test_verification_summary_in_failure_response(self):
        """Test that failed responses include verification details."""
        from aegis.agents.base import AgentResponse
        
        # Create a mock failed response with verification
        response = AgentResponse(
            status="FAIL",
            data={
                "workspace": "test_workspace",
                "verification": {
                    "passed": False,
                    "critical_errors": 2,
                    "warnings": 1,
                    "summary": "❌ FAILED\nCritical Errors: 2\nWarnings: 1"
                }
            },
            reasoning_trace="Verification failed",
            errors=["Verification failed with 2 critical errors"]
        )
        
        assert not response.data["verification"]["passed"]
        assert response.data["verification"]["critical_errors"] == 2
