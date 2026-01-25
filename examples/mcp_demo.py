#!/usr/bin/env python3
"""Quick demo of MCP integration in Aegis-CLI.

This script demonstrates how to:
1. Load MCP configuration
2. Create agents with MCP servers
3. Use the orchestrator to equip agents

Note: This is a demo script - actual MCP server connections would require
proper environment variables and running MCP servers.
"""

from aegis.agents.coder import CoderAgent
from aegis.agents.orchestrator import OrchestratorAgent
from aegis.core.mcp_client import load_mcp_config, filter_servers_by_name


def demo_basic_mcp_loading() -> None:
    """Demonstrate basic MCP config loading."""
    print("=" * 60)
    print("DEMO 1: Basic MCP Configuration Loading")
    print("=" * 60)
    
    try:
        servers = load_mcp_config("mcp_config.json")
        print(f"\n✓ Successfully loaded {len(servers)} MCP servers:")
        for server in servers:
            print(f"  • {server.name} ({server.transport})")
            if server.transport == "stdio":
                print(f"    Command: {server.command} {' '.join(server.args)}")
            else:
                print(f"    URL: {server.url}")
    except FileNotFoundError:
        print("\n✗ mcp_config.json not found")
    except Exception as e:
        print(f"\n✗ Error loading config: {e}")
    
    print()


def demo_agent_with_mcp() -> None:
    """Demonstrate creating an agent with MCP servers."""
    print("=" * 60)
    print("DEMO 2: Agent with MCP Servers")
    print("=" * 60)
    
    try:
        # Load all servers
        all_servers = load_mcp_config("mcp_config.json")
        
        # Filter to GitHub only
        github_servers = filter_servers_by_name(all_servers, ["github"])
        
        # Create CoderAgent with GitHub MCP server
        coder = CoderAgent()
        coder.mcp_servers = github_servers
        
        print(f"\n✓ Created CoderAgent with MCP support")
        print(f"  Agent name: {coder.name}")
        print(f"  MCP servers: {coder.get_mcp_server_names()}")
        print(f"  Number of servers: {len(coder.mcp_servers)}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    print()


def demo_orchestrator_pattern() -> None:
    """Demonstrate orchestrator pattern for equipping agents."""
    print("=" * 60)
    print("DEMO 3: Orchestrator Pattern")
    print("=" * 60)
    
    try:
        # Create orchestrator with MCP config
        orchestrator = OrchestratorAgent(mcp_config_path="mcp_config.json")
        
        print(f"\n✓ Created Orchestrator with MCP configuration")
        
        # Get servers for different agents
        coder_servers = orchestrator.get_mcp_servers_for_agent(
            "coder",
            server_names=["github", "google-search"]
        )
        
        print(f"\n  Servers for CoderAgent:")
        for server in coder_servers:
            print(f"    • {server.name}")
        
        # Create CoderAgent with those servers
        coder = CoderAgent()
        coder.mcp_servers = coder_servers
        
        print(f"\n  CoderAgent equipped with: {coder.get_mcp_server_names()}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
    
    print()


def demo_mcp_context_manager() -> None:
    """Demonstrate the run_with_mcp context manager."""
    print("=" * 60)
    print("DEMO 4: MCP Context Manager (Structure)")
    print("=" * 60)

    print("""
The run_with_mcp() context manager provides a clean way to use MCP servers:

    async with agent.run_with_mcp() as mcp_toolsets:
        # mcp_toolsets contains MCP server instances
        # Use them as toolsets with PydanticAI Agent:

        pydantic_agent = Agent(
            model="claude-3-5-sonnet-20241022",
            toolsets=mcp_toolsets,
            system_prompt=agent.get_system_prompt()
        )

        result = await pydantic_agent.run("Your prompt here")

Benefits:
  • Automatic server lifecycle management
  • MCP servers are passed as toolsets to PydanticAI
  • Cleanup happens automatically on context exit
  • Works with both stdio and SSE transports
    """)


def main() -> None:
    """Run all demos."""
    print("\n" + "=" * 60)
    print("AEGIS-CLI MCP INTEGRATION DEMO")
    print("=" * 60 + "\n")
    
    demo_basic_mcp_loading()
    demo_agent_with_mcp()
    demo_orchestrator_pattern()
    demo_mcp_context_manager()
    
    print("=" * 60)
    print("Demo complete! See MCP_INTEGRATION.md for full documentation.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
