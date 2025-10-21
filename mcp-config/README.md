# PowerBI MCP Server Configuration

This directory contains configuration files for using the PowerBI MCP Server with various MCP clients.

## Configuration Files

### `mcp.json` - General MCP Configuration
Standard MCP server configuration for most MCP clients.

### `claude-desktop-config.json` - Claude Desktop
Configuration for Anthropic's Claude Desktop application.

### `continue-config.json` - Continue.dev
Configuration for the Continue.dev VSCode extension.

## Setup Instructions

### For Claude Desktop
1. Copy the contents of `claude-desktop-config.json`
2. Add to your Claude Desktop configuration file:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

### For Continue.dev
1. Copy the contents of `continue-config.json`
2. Add to your Continue configuration file:
   - **VSCode**: `.continue/config.json` in your workspace

### For Other MCP Clients
Use the `mcp.json` configuration as a reference for setting up the server.

## Environment Variables

The server requires these environment variables:
- `PYTHONNET_RUNTIME=coreclr` - Required for .NET integration
- `USE_AZURE_CLI=true` - Enable Azure CLI authentication
- `ADOMD_LIB_DIR` - Path to ADOMD.NET libraries (auto-detected if not set)

## Server Details

- **Endpoint**: `http://127.0.0.1:8000/sse`
- **Protocol**: Server-Sent Events (SSE)
- **Authentication**: Azure CLI (no client secret needed)
- **Tools**: `connect`, `list_tables`, `describe_table`, `query_data`, `natural_language_query`

## Power BI Connection

Use the `connect` tool with these parameters:
```json
{
  "xmla_endpoint": "powerbi://api.powerbi.com/v1.0/myorg/YourWorkspaceName",
  "initial_catalog": "YourDatasetName",
  "tenant_id": "your-azure-tenant-id"
}
```

No client secret is required when using Azure CLI authentication.
