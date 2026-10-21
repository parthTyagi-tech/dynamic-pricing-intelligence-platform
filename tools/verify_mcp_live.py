import asyncio
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parents[1] / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.mcp.server import mcp


async def main():
    print("=" * 60)
    print("       KLYPUP MCP SERVER LIVE AGENT VERIFICATION")
    print("=" * 60)

    # 1. Tool Discovery Check (tools/list)
    tools = mcp._tool_manager.list_tools()
    print(f"\n[OK] FastMCP discovered {len(tools)} tools available for AI agents:")
    for t in tools:
        doc = (t.description or "").strip().splitlines()[0]
        print(f"  • {t.name:<34} -> {doc}")

    # 2. Resource Discovery Check (resources/list)
    resources = mcp._resource_manager.list_resources()
    templates = mcp._resource_manager.list_templates()
    print(f"\n[OK] FastMCP discovered {len(resources) + len(templates)} resources:")
    for r in resources:
        print(f"  • {str(r.uri):<38} (Static Resource)")
    for tmpl in templates:
        print(f"  • {tmpl.uri_template:<38} (Resource Template)")

    # 3. Prompt Discovery Check (prompts/list)
    prompts = mcp._prompt_manager.list_prompts()
    print(f"\n[OK] FastMCP discovered {len(prompts)} workflow prompts:")
    for p in prompts:
        print(f"  • {p.name:<34} -> {(p.description or '').strip().splitlines()[0]}")

    # 4. Live Tool Execution via MCP Tool Manager
    print("\n" + "=" * 60)
    print(" [AGENT ACTION] Invoking 'check_or_reset_circuit_breakers'...")
    print("=" * 60)
    tool_fn = mcp._tool_manager.get_tool("check_or_reset_circuit_breakers")
    tool_result = await tool_fn.run(arguments={"reset": False, "run_canaries": False})

    print(f"\n[SUCCESS] Response from tool 'check_or_reset_circuit_breakers':")
    print(f"  Total Platforms Checked: {tool_result.get('total_platforms')}")
    print(f"  Reset Executed:          {tool_result.get('reset_executed')}")
    print("\n  Sample Platform Sensors Health:")
    for p in tool_result.get("platforms", [])[:6]:
        print(f"    - {p['platform']:<15} | Circuit: {p['circuit_state'].upper():<9} | Failures: {p['failure_count_last_hour']}")

    # 5. Live Resource Read Check
    print("\n" + "=" * 60)
    print(" [AGENT ACTION] Reading resource 'klypup://scrapers/health'...")
    print("=" * 60)
    res_obj = await mcp._resource_manager.get_resource("klypup://scrapers/health")
    content = await res_obj.read()
    health_list = json.loads(content)
    print(f"[SUCCESS] Resource content returned valid JSON array with {len(health_list)} platform records.")

    print("\n" + "=" * 60)
    print("     ALL MCP PROTOCOL CHECKS PASSED: READY FOR AGENTS")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
