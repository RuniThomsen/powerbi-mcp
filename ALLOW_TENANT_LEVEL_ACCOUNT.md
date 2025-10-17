# ALLOW_TENANT_LEVEL_ACCOUNT Configuration

## Overview

The `ALLOW_TENANT_LEVEL_ACCOUNT` environment variable explicitly enables support for Azure AD tenant-level accounts that don't have Azure subscriptions.

## Why This Exists

**Power BI authentication only requires Azure AD (tenant) access**, not Azure subscriptions.

Many users have:
- Consultant/contractor accounts
- External user accounts (e.g., `-ext@` accounts)
- Power BI-only licenses
- Tenant access without subscription permissions

These accounts show:
```bash
$ az account show
{
  "subscriptions": "N/A(tenant level account)",
  "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
  "user": "runi.thomsen-ext@konicaminolta.dk"
}
```

## Configuration

### Method 1: MCP Configuration Files (Recommended)

**`.vscode/mcp.json`:**
```json
{
  "servers": {
    "powerbi-mcp": {
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["-u", "${workspaceFolder}/src/server_enhanced.py"],
      "env": {
        "USE_AZURE_CLI": "true",
        "ALLOW_TENANT_LEVEL_ACCOUNT": "true",
        "AZURE_TENANT_ID": "your-tenant-id",
        ...
      }
    }
  }
}
```

**`.vscode/settings.json`:**
```json
{
  "github.copilot.chat.experimental.mcpServers": {
    "powerbi-mcp": {
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["-u", "${workspaceFolder}/src/server_enhanced.py"],
      "env": {
        "USE_AZURE_CLI": "true",
        "ALLOW_TENANT_LEVEL_ACCOUNT": "true",
        "AZURE_TENANT_ID": "your-tenant-id",
        ...
      }
    }
  }
}
```

### Method 2: Environment Variable

**Windows (PowerShell):**
```powershell
$env:ALLOW_TENANT_LEVEL_ACCOUNT = "true"
```

**Windows (CMD):**
```cmd
set ALLOW_TENANT_LEVEL_ACCOUNT=true
```

**Linux/Mac:**
```bash
export ALLOW_TENANT_LEVEL_ACCOUNT=true
```

### Method 3: .env File

```bash
# .env file in project root
ALLOW_TENANT_LEVEL_ACCOUNT=true
USE_AZURE_CLI=true
AZURE_TENANT_ID=your-tenant-id
```

## What It Does

### When Set to `true`

1. **Logs confirmation message:**
   ```
   INFO - Tenant-level accounts allowed (no Azure subscription required)
   ```

2. **Suppresses subscription warnings** in validation scripts

3. **Documents that subscription-less operation is intentional**

4. **Clarifies authentication requirements** in error messages

### When Not Set (or set to `false`)

- Server still works fine with tenant-level accounts
- No functional difference in authentication
- May see informational messages about account type

## Authentication Flow

The authentication flow is **identical** regardless of this setting:

```
MCP Server needs token
    ↓
Calls: az account get-access-token --tenant <tenant_id> --resource <powerbi_api>
    ↓
Azure CLI checks:
  ✅ Is user authenticated to tenant?
  ✅ Does user have Power BI permissions?
  ❌ NOT checked: Azure subscription access
    ↓
Token issued
    ↓
Power BI API call succeeds
```

## Requirements

### What You NEED

✅ **Azure AD tenant access**
- Login command: `az login --tenant <your-tenant-id>`
- Account status: Shows tenant ID in `az account show`

✅ **Power BI permissions**
- Workspace access
- Dataset read permissions
- Appropriate Power BI license

✅ **Azure CLI installed and logged in**
- `az --version` works
- `az account show` returns your account info

### What You DON'T NEED

❌ **Azure subscription**
- No VMs, storage, or other Azure resources needed
- Power BI is a separate service

❌ **Subscription-level permissions**
- Resource group access
- ARM (Azure Resource Manager) permissions

❌ **Azure portal access**
- Power BI accessed via api.powerbi.com
- Authentication via Azure AD only

## Verification

### Check Your Account Type

```bash
# Show account info
az account show --query "{tenant:tenantId, user:user.name, subscription:name}"

# Output for tenant-level account:
# {
#   "subscription": "N/A(tenant level account)",
#   "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
#   "user": "runi.thomsen-ext@konicaminolta.dk"
# }
```

### Test Token Acquisition

```bash
# This should succeed even without subscription
az account get-access-token --resource https://analysis.windows.net/powerbi/api

# Expected output:
# {
#   "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGc...",  # Long JWT token
#   "expiresOn": "2025-10-04 10:30:00",
#   "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
#   "tokenType": "Bearer"
# }
```

### Test MCP Server

```bash
# Run REST API test
python test_rest_only.py

# Expected output:
# ✅ Found XX workspaces
# ✅ REST API test completed successfully
```

## Troubleshooting

### "No subscriptions found"

**This is NORMAL for tenant-level accounts!**

✅ **Ignore this message** - It doesn't affect Power BI functionality

If you see this during authentication:
1. Set `ALLOW_TENANT_LEVEL_ACCOUNT=true` to confirm it's intentional
2. Verify you can get Power BI tokens: `az account get-access-token --resource https://analysis.windows.net/powerbi/api`
3. Test MCP server: `python test_rest_only.py`

### Authentication Still Fails

**Check:**
1. Logged in to correct tenant:
   ```bash
   az account show --query tenantId
   ```

2. Can get Power BI token:
   ```bash
   az account get-access-token --resource https://analysis.windows.net/powerbi/api
   ```

3. Have Power BI access:
   - Visit https://app.powerbi.com
   - Can you see workspaces?

### Server Logs Show Subscription Errors

If server logs mention subscriptions:
1. Set `ALLOW_TENANT_LEVEL_ACCOUNT=true`
2. Reload VS Code window
3. Check logs for "Tenant-level accounts allowed" message

## Related Configuration

### Minimal MCP Configuration for Tenant-Level Accounts

```json
{
  "servers": {
    "powerbi-mcp": {
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["-u", "${workspaceFolder}/src/server_enhanced.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "USE_AZURE_CLI": "true",
        "ALLOW_TENANT_LEVEL_ACCOUNT": "true",
        "AZURE_TENANT_ID": "17f69c66-2114-4826-9fb1-6e496607aebc",
        "PYTHONNET_RUNTIME": "coreclr",
        "ADOMD_LIB_DIR": "C:\\Users\\...\\microsoft.analysisservices.adomdclient\\...\\lib\\net8.0"
      }
    }
  }
}
```

### Azure CLI Login for Tenant-Level Accounts

```bash
# Login to specific tenant
az login --tenant 17f69c66-2114-4826-9fb1-6e496607aebc

# Verify login
az account show

# Test Power BI access
az account get-access-token --resource https://analysis.windows.net/powerbi/api
```

## Summary

| Setting | Value | Effect |
|---------|-------|--------|
| `ALLOW_TENANT_LEVEL_ACCOUNT=true` | Enabled | Logs confirmation, documents intent |
| `ALLOW_TENANT_LEVEL_ACCOUNT=false` | Disabled | No change in functionality |
| Not set | Default | Same as `false` |

**Key Point:** This setting is **informational and documentational**. The server works with tenant-level accounts regardless of this setting. It exists to:
- Make configuration intent explicit
- Suppress warnings in validation scripts  
- Document that subscription-less operation is supported and expected

---

**Your configuration with `ALLOW_TENANT_LEVEL_ACCOUNT=true` is now active! ✅**
