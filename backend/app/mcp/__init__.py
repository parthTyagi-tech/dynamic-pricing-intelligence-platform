"""
Klypup Model Context Protocol (MCP) Server package.
Exposes MCP tools, resources, and prompts for external AI orchestrators.
"""

from app.mcp.server import mcp, create_mcp_server, _get_flask_app

__all__ = ["mcp", "create_mcp_server", "_get_flask_app"]
