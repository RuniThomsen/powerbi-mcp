# Azure CLI Authentication - Tenant-Level Accounts

## Your Account Type

You have a **tenant-level account** which means:
- ✅ You have access to Azure AD tenant: `17f69c66-2114-4826-9fb1-6e496607aebc`
- ✅ You can authenticate against the tenant
- ✅ You have Power BI access through tenant permissions
- ❌ You don't have an Azure subscription (and you don't need one!)

```bash
$ az account show
{
  "subscriptions": "N/A(tenant level account)",
  "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
  "user": "runi.thomsen-ext@konicaminolta.dk"
}
```

## Why This Works

### Power BI Authentication Doesn't Require Subscriptions

Power BI uses **Azure AD (Entra ID) authentication**, not Azure Resource Manager (ARM) subscriptions.

**What you need:**
- ✅ Azure AD tenant access
- ✅ Power BI license/permissions
- ✅ Azure CLI logged in to the tenant

**What you DON'T need:**
- ❌ Azure subscription
- ❌ Resource groups
- ❌ Azure resources

### How the MCP Server Handles This

The server uses `az account get-access-token` with **tenant-based authentication**:

```bash
# This works WITHOUT a subscription
az account get-access-token \
  --tenant 17f69c66-2114-4826-9fb1-6e496607aebc \
  --resource https://analysis.windows.net/powerbi/api
```

**Key points:**
1. `--tenant` parameter specifies which Azure AD tenant to authenticate against
2. `--resource` parameter requests Power BI API scope (not ARM subscription scope)
3. Token is issued based on **tenant permissions**, not subscription access

### Authentication Flow

```
User logged in to Azure AD tenant
    ↓
MCP Server requests token
    ↓
az account get-access-token --tenant <tenant_id> --resource <powerbi_scope>
    ↓
Azure AD checks:
  - Is user authenticated to this tenant? ✅
  - Does user have permission to access Power BI? ✅
  - (Does NOT check: subscription access)
    ↓
Token issued with Power BI permissions
    ↓
MCP Server uses token to call Power BI REST API
    ↓
Power BI validates token and returns data
```

## Common Scenarios

### Scenario 1: Tenant-Level Account (Your Case)

**Account Type:** External consultant, contractor, or Power BI-only user

**Status:**
```bash
$ az account show
{
  "subscriptions": "N/A(tenant level account)",
  "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
  "user": "runi.thomsen-ext@konicaminolta.dk"
}
```

**What Works:**
- ✅ Power BI workspaces
- ✅ Power BI datasets
- ✅ DAX queries via REST API
- ✅ XMLA connections (if enabled)

**What Doesn't Work:**
- ❌ Azure Resource Manager operations (creating VMs, storage, etc.)
- ❌ Azure subscription-level commands (`az vm list`, `az storage account list`, etc.)

**MCP Server Status:** ✅ **Fully Functional**

### Scenario 2: Subscription-Based Account

**Account Type:** Full Azure user with subscription access

**Status:**
```bash
$ az account show
{
  "subscriptions": "My-Subscription-Name",
  "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
  "user": "john.doe@company.com"
}
```

**What Works:**
- ✅ Everything from Scenario 1, PLUS
- ✅ Azure Resource Manager operations
- ✅ Azure CLI commands for all services

**MCP Server Status:** ✅ **Fully Functional** (same as Scenario 1)

## Why "N/A(tenant level account)" is Normal

### This is NOT an error!

Azure CLI shows this when:
1. You logged in with `az login --tenant <tenant_id>` (tenant-focused login)
2. Your account doesn't have Azure subscription access
3. You're an external user (like `-ext@` accounts)

### Proof It Works

```bash
# This succeeds even without subscription
$ az account get-access-token --resource https://analysis.windows.net/powerbi/api
{
  "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expiresOn": "2025-10-04 10:30:00",
  "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
  "tokenType": "Bearer"
}

# And the MCP server successfully lists workspaces
✅ Found 17 Power BI workspaces
```

## Technical Details

### Token Scopes

**Power BI REST API:**
```bash
# Using modern --scope syntax
az account get-access-token --scope https://analysis.windows.net/powerbi/api/.default

# Using legacy --resource syntax (for older Azure CLI)
az account get-access-token --resource https://analysis.windows.net/powerbi/api
```

**Azure Resource Manager (requires subscription):**
```bash
# This would fail for tenant-level accounts
az account get-access-token --resource https://management.azure.com/
# Error: No subscriptions found
```

### MCP Server Implementation

The server tries both scope formats for compatibility:

```python
# From src/server_enhanced.py, line ~360

# First try modern --scope syntax
result = subprocess.run([
    az_path, "account", "get-access-token",
    "--tenant", tenant_id,
    "--scope", scope,  # e.g., "https://analysis.windows.net/powerbi/api/.default"
    "--query", "accessToken",
    "--output", "tsv"
], ...)

# Fallback to legacy --resource if --scope fails
legacy = subprocess.run([
    az_path, "account", "get-access-token",
    "--tenant", tenant_id,
    "--resource", resource,  # e.g., "https://analysis.windows.net/powerbi/api"
    "--query", "accessToken",
    "--output", "tsv"
], ...)
```

## Troubleshooting

### "No subscriptions found" Error

**If you see this when running MCP server:**
- ✅ **Ignore it** - This is normal for tenant-level accounts
- ✅ The server will still work for Power BI operations
- ✅ Token acquisition will succeed

**If you see this when trying to use Azure resources:**
- ❌ You don't have Azure subscription access
- ✅ This doesn't affect Power BI functionality
- ℹ️ Contact your Azure admin if you need subscription access

### Login Command for Tenant-Level Accounts

```bash
# Correct way to login (what you already did)
az login --tenant 17f69c66-2114-4826-9fb1-6e496607aebc

# This logs you into the specific tenant
# No subscription selection needed!
```

### Verify Your Setup

```bash
# 1. Check you're logged in to correct tenant
az account show --query "{tenant:tenantId, user:user.name}"

# Expected output:
# {
#   "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
#   "user": "runi.thomsen-ext@konicaminolta.dk"
# }

# 2. Test Power BI token acquisition
az account get-access-token --resource https://analysis.windows.net/powerbi/api

# Expected output:
# {
#   "accessToken": "eyJ0eXAiOiJKV1QiLCJhbGc...",  <-- Long JWT token
#   "expiresOn": "...",
#   "tenant": "17f69c66-2114-4826-9fb1-6e496607aebc",
#   "tokenType": "Bearer"
# }

# 3. Test MCP server
python test_rest_only.py

# Expected output:
# ✅ Found 17 workspaces
```

## Summary

### Your Configuration

| Setting | Value | Status |
|---------|-------|--------|
| Account Type | Tenant-level | ✅ Perfect for Power BI |
| Azure Subscription | N/A | ✅ Not needed |
| Tenant ID | `17f69c66-2114-4826-9fb1-6e496607aebc` | ✅ Correct |
| User | `runi.thomsen-ext@konicaminolta.dk` | ✅ Logged in |
| Power BI Access | Yes | ✅ Working (17 workspaces) |
| MCP Server | Running | ✅ Fully functional |

### Key Takeaways

1. ✅ **"N/A(tenant level account)" is normal** - Not an error
2. ✅ **Power BI doesn't need Azure subscriptions** - Tenant access is enough
3. ✅ **Your setup is correct** - Everything is working as designed
4. ✅ **No changes needed** - Keep using `az login --tenant <tenant_id>`

---

**Your authentication setup is perfect for Power BI MCP server usage! 🎉**
