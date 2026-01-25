"""Example: Using MCP Servers with CoderAgent

This example demonstrates how to equip the CoderAgent with external tools
via MCP (Model Context Protocol) servers, such as GitHub or Google Search.
"""

import asyncio
from pathlib import Path

from aegis.agents.coder import CoderAgent
from aegis.agents.base import AgentTask
from aegis.core.mcp_client import load_mcp_config, filter_servers_by_name


async def example_coder_with_github_mcp() -> None:
    """Example: CoderAgent with GitHub MCP server.

    This example shows how to:
    1. Load MCP configuration from mcp_config.json
    2. Filter to only GitHub server
    3. Create CoderAgent with MCP servers
    4. Use the agent with MCP toolsets available
    """
    print("=== Example: CoderAgent with GitHub MCP ===\n")

    # Load MCP configuration
    try:
        mcp_servers = load_mcp_config("mcp_config.json")
        print(f"Loaded {len(mcp_servers)} MCP servers from config")
    except FileNotFoundError:
        print("Error: mcp_config.json not found")
        return

    # Filter to only GitHub server
    github_servers = filter_servers_by_name(mcp_servers, ["github"])
    print(f"Filtered to GitHub server: {[s.name for s in github_servers]}\n")

    # Create CoderAgent with MCP servers
    coder = CoderAgent()
    coder.mcp_servers = github_servers

    # Create a task
    task = AgentTask(
        id="example-1",
        type="code",
        payload={
            "description": "Create a function to fetch GitHub repository info",
            "file_path": "github_utils.py"
        }
    )

    # Use the agent with MCP toolsets
    print("Running agent with MCP toolsets...")
    async with coder.run_with_mcp() as mcp_toolsets:
        print(f"Available MCP toolsets: {len(mcp_toolsets)}")

        # In a real scenario, you would use these toolsets with PydanticAI:
        # from pydantic_ai import Agent
        #
        # pydantic_agent = Agent(
        #     model="claude-3-5-sonnet-20241022",
        #     toolsets=mcp_toolsets,
        #     system_prompt=coder.get_system_prompt()
        # )
        # result = await pydantic_agent.run(
        #     f"Generate code: {task.payload['description']}"
        # )

        # For this example, just process the task normally
        response = await coder.process(task)
        print(f"Agent response: {response.status}")
        print(f"Reasoning: {response.reasoning_trace}\n")


async def example_coder_with_multiple_mcp_servers() -> None:
    """Example: CoderAgent with multiple MCP servers.

    This example shows how to equip the CoderAgent with multiple
    MCP servers (GitHub and Google Search) for richer tool access.
    """
    print("=== Example: CoderAgent with Multiple MCP Servers ===\n")

    # Load MCP configuration
    try:
        mcp_servers = load_mcp_config("mcp_config.json")
    except FileNotFoundError:
        print("Error: mcp_config.json not found")
        return

    # Filter to GitHub and Google Search servers
    selected_servers = filter_servers_by_name(
        mcp_servers,
        ["github", "google-search"]
    )
    print(f"Selected servers: {[s.name for s in selected_servers]}\n")

    # Create CoderAgent with MCP servers
    coder = CoderAgent()
    coder.mcp_servers = selected_servers

    # Create a task
    task = AgentTask(
        id="example-2",
        type="code",
        payload={
            "description": "Research and implement best practices for API design",
            "file_path": "api_design.py"
        }
    )

    # Use the agent with MCP toolsets
    print("Running agent with MCP toolsets...")
    async with coder.run_with_mcp() as mcp_toolsets:
        print(f"Available MCP toolsets from {len(selected_servers)} servers: {len(mcp_toolsets)}")

        # Process task
        response = await coder.process(task)
        print(f"Agent response: {response.status}")
        print(f"Reasoning: {response.reasoning_trace}\n")


async def example_orchestrator_equipping_agents() -> None:
    """Example: Orchestrator equipping agents with MCP tools.
    
    This example shows how the Orchestrator can selectively equip
    different agents with different MCP servers based on their needs.
    """
    print("=== Example: Orchestrator Equipping Agents ===\n")
    
    from aegis.agents.orchestrator import OrchestratorAgent
    
    # Create orchestrator with MCP config
    orchestrator = OrchestratorAgent(mcp_config_path="mcp_config.json")
    
    # Get appropriate MCP servers for CoderAgent
    # For coder, we might want GitHub access
    coder_servers = orchestrator.get_mcp_servers_for_agent(
        "coder",
        server_names=["github"]
    )
    print(f"CoderAgent equipped with: {[s.name for s in coder_servers]}")
    
    # Create CoderAgent with those servers
    coder = CoderAgent()
    coder.mcp_servers = coder_servers
    
    print(f"MCP servers on coder: {coder.get_mcp_server_names()}\n")


async def main() -> None:
    """Run all examples."""
    await example_coder_with_github_mcp()
    print("\n" + "="*60 + "\n")
    
    await example_coder_with_multiple_mcp_servers()
    print("\n" + "="*60 + "\n")
    
    await example_orchestrator_equipping_agents()


if __name__ == "__main__":
    asyncio.run(main())
