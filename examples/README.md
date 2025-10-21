# PowerBI MCP Examples

This directory contains example scripts demonstrating how to use the PowerBI MCP server's connectivity features.

## Available Examples

### 1. REST API Example (`rest_api_example.py`)
Demonstrates how to use the Power BI REST API without XMLA connection.

**Features:**
- Direct access to Power BI service (powerbi.com)
- List workspaces and datasets
- Execute DAX queries via REST API
- Azure AD authentication

**Usage:**
```bash
python examples/rest_api_example.py
```

### 2. SSAS Interactive Example (`ssas_interactive_example.py`)
Interactive script to connect and query on-premises SQL Server Analysis Services (SSAS) servers.

**Features:**
- Windows authentication for internal SSAS servers
- XMLA endpoint connectivity
- Interactive querying of data models
- Table and column metadata exploration

**Usage:**
```bash
python examples/ssas_interactive_example.py
```

### 3. Windows Auth Example (`windows_auth_example.py`)
Quick test of Windows authentication without MCP protocol overhead.

**Features:**
- Direct Windows authentication to SSAS
- Minimal setup for testing connectivity
- Useful for troubleshooting authentication issues

**Usage:**
```bash
python examples/windows_auth_example.py
```

## Prerequisites

All examples require:
- Python 3.11+
- Virtual environment activated (`.venv`)
- Required environment variables set (see main README.md)
- ADOMD.NET libraries installed

## Environment Setup

Before running examples, ensure these environment variables are set:

```bash
export PYTHONNET_RUNTIME=coreclr
export ADOMD_LIB_DIR=/path/to/adomdclient/lib
export AZURE_TENANT_ID=your-tenant-id  # For Azure AD auth
```

See `docs/setup/windows-setup.md` for detailed setup instructions.
