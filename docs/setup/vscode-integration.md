# VS Code Integration Guide

This guide covers how to use the PowerBI MCP server within VS Code with GitHub Copilot and other development features.

## Prerequisites

1. **VS Code Extensions**: Install the recommended extensions (VS Code will prompt when opening the workspace):
   - Python extension pack (python, debugpy, black-formatter, isort, flake8)
   - GitHub Copilot and Copilot Chat
   - PowerShell extension

2. **Environment Setup**: Ensure your environment is configured:
   ```powershell
   # Activate the virtual environment
   .\.venv\Scripts\Activate.ps1
   
   # Verify setup
   python scripts/validate_setup.py
   ```

## GitHub Copilot Integration

### Configuration

The workspace is pre-configured for GitHub Copilot MCP integration:

- **MCP Server Config**: `.vscode/mcp.json` defines the PowerBI MCP server
- **Copilot Settings**: `.vscode/settings.json` enables experimental MCP features
- **Context Providers**: Configured to use PowerBI data as context for Copilot

### Using PowerBI Data with Copilot

1. **Start the MCP Server**:
   - Use VS Code Task: `Ctrl+Shift+P` → "Tasks: Run Task" → "Start PowerBI MCP Server"
   - Or use the debug configuration: `F5` → "PowerBI MCP Server"

2. **Chat with Copilot**:
   ```
   @workspace What tables are available in the CN_DEV Power BI model?
   
   @workspace Show me the relationships between tables in the Model dataset
   
   @workspace Generate Python code to query the sales data from Power BI
   ```

3. **Code Generation**:
   Copilot can now generate code that uses your actual PowerBI schema and data structure.

## Available VS Code Tasks

Access via `Ctrl+Shift+P` → "Tasks: Run Task":

- **Start PowerBI MCP Server**: Launch the server on port 8000
- **Setup PowerBI MCP Environment**: Install dependencies and validate setup
- **Validate PowerBI MCP Setup**: Run comprehensive validation
- **Test MCP Connectivity**: Test server connection and protocol

## Debug Configurations

Available debug configurations (`F5` or Debug panel):

1. **PowerBI MCP Server**: Standard server launch
2. **PowerBI MCP Server (Debug)**: Enhanced debugging with pre-launch validation
3. **Run Validation Script**: Debug the setup validation process

## Development Workflow

### 1. Starting Development
```bash
# Open in VS Code
code .

# VS Code will prompt to install recommended extensions
# Accept the installation

# Start the MCP server
# Use Ctrl+Shift+P → "Tasks: Run Task" → "Start PowerBI MCP Server"
```

### 2. Testing Changes
```bash
# Run validation
# Use task: "Validate PowerBI MCP Setup"

# Test connectivity  
# Use task: "Test MCP Connectivity"

# Run full test suite
python -m pytest -v
```

### 3. Debugging
- Use the "PowerBI MCP Server (Debug)" configuration for enhanced debugging
- Set breakpoints in VS Code
- Use integrated terminal for testing

## GitHub Copilot Context

The MCP integration provides Copilot with:

- **Schema Information**: Table structures, column names, data types
- **Relationship Data**: How tables are connected in your Power BI model
- **Query Capabilities**: Understanding of what data can be retrieved
- **Authentication Context**: Knowledge of Azure CLI authentication setup

## Troubleshooting

### MCP Server Not Starting
1. Check environment variables are set:
   ```powershell
   $env:ADOMD_LIB_DIR
   $env:PYTHONNET_RUNTIME
   ```

2. Validate setup:
   ```bash
   python scripts/validate_setup.py
   ```

### Copilot Not Seeing MCP Server
1. Restart VS Code
2. Check `.vscode/mcp.json` configuration
3. Verify server is running on port 8000
4. Check VS Code output panel for MCP errors

### Authentication Issues
1. Verify Azure CLI login:
   ```bash
   az account show
   ```

2. Test authentication:
   ```bash
   python scripts/test_mcp_connectivity.py
   ```

## Advanced Configuration

### Custom MCP Settings
Modify `.vscode/mcp.json` for custom configurations:

```json
{
  "servers": {
    "powerbi-mcp": {
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["${workspaceFolder}/src/server_enhanced.py"],
      "env": {
        "PYTHONNET_RUNTIME": "coreclr",
        "USE_AZURE_CLI": "true",
        "CUSTOM_WORKSPACE": "YOUR_WORKSPACE",
        "CUSTOM_MODEL": "YOUR_MODEL"
      }
    }
  }
}
```

### Environment Variables
Override defaults in `.vscode/settings.json`:

```json
{
  "terminal.integrated.env.windows": {
    "ADOMD_LIB_DIR": "C:\\path\\to\\your\\adomd\\libs",
    "PYTHONNET_RUNTIME": "coreclr",
    "USE_AZURE_CLI": "true"
  }
}
```

## Integration with Other Tools

### Continue.dev
Configuration available in `mcp-config/continue-dev.json`

### Claude Desktop  
Configuration available in `mcp-config/claude-desktop.json`

### Manual MCP Setup
Use the installer script:
```python
python scripts/install_mcp.py
```

## Best Practices

1. **Keep Server Running**: Start the MCP server at the beginning of your session
2. **Use Tasks**: Leverage VS Code tasks for common operations
3. **Debug Mode**: Use debug configurations for development
4. **Validate Frequently**: Run validation after environment changes
5. **Context Awareness**: Use `@workspace` in Copilot chats for PowerBI context

## Support

- Check `docs/TROUBLESHOOTING.md` for common issues
- Use validation scripts for diagnostics
- Review server logs in VS Code terminal
- Test MCP connectivity with provided scripts
