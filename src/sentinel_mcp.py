"""
Sentinel Governed MCP Server (FastMCP)
Exposes ONLY whitelisted, read-only DuckDB tools to external AI clients.
"""
from fastmcp import FastMCP
from src.sentinel_agent import (
    initialize_demo_tables,
    list_allowed_tables,
    get_table_schema,
    run_readonly_sql,
)

# 1. Initialize the DuckDB tables and create the MCP Server
initialize_demo_tables()
mcp = FastMCP(name="Sentinel Governed Data Agent")

# 2. Register your 3 Guardrailed Functions as MCP Tools
@mcp.tool
def sentinel_list_tables() -> list[str]:
    """List ONLY governed Sentinel tables (blocks raw bronze/silver tables)."""
    return list_allowed_tables()

@mcp.tool
def sentinel_get_schema(table_name: str) -> str:
    """Get column names and types for an allowed Sentinel table."""
    return get_table_schema(table_name)

@mcp.tool
def sentinel_query_sql(query: str) -> str:
    """Run a strictly READ-ONLY SELECT query against allowed Sentinel tables."""
    return run_readonly_sql(query)

if __name__ == "__main__":
    # Runs over standard stdio (for Claude Desktop / Cursor)
    # Or use mcp.run(transport="http", port=8000) for remote HTTP clients
    mcp.run()
