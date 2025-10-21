# Power BI XMLA Authentication Solution

## Overview

This document explains the solution for enabling XMLA connectivity to Power BI datasets using MSAL device code authentication on Windows with pythonnet.

## Problem Summary

Azure CLI authentication was failing to connect to Power BI XMLA endpoints despite working perfectly in DAX Studio. The investigation revealed multiple interrelated issues:

### 1. Token Scope Issue
- **Root Cause**: Azure CLI tokens only include `user_impersonation` scope
- **Requirement**: Power BI XMLA requires `Dataset.Read.All` or similar dataset-specific scopes
- **Why DAX Studio Works**: It uses Microsoft's first-party client ID with pre-consented Power BI scopes

### 2. pythonnet/.NET Compatibility Issue
- **Root Cause**: ADOMD.NET's `net8.0` assemblies use .NET Core types (like `System.MarshalByRefObject` from `System.Runtime`) that aren't available in pythonnet's .NET Framework runtime on Windows
- **Symptom**: Assembly loads successfully but pythonnet can't enumerate types for imports
- **Error**: `Could not load type 'System.MarshalByRefObject' from assembly 'System.Runtime'`

### 3. Assembly Loading Order Issue
- **Root Cause**: pythonnet must have ADOMD.NET assemblies in the Windows PATH before initializing the .NET runtime
- **Symptom**: Even after `clr.AddReference()`, pythonnet can't import from Microsoft.AnalysisServices namespaces
- **Solution**: Add ADOMD directory to PATH before any `import clr` statements

## Solution Implementation

### 1. Use MSAL Device Code Flow

Since users cannot register custom Entra apps, we use Power BI's public client ID for device code authentication:

```python
from msal import PublicClientApplication

# Power BI public client (Power Query for Excel)
CLIENT_ID = "a672d62c-fc7b-4e81-a576-e60dc46e951d"
AUTHORITY = f"https://login.microsoftonline.com/{tenant_id}"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]

app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)
flow = app.initiate_device_flow(scopes=SCOPES)
print(flow["message"])  # User completes authentication in browser
result = app.acquire_token_by_device_flow(flow)
token = result["access_token"]
```

### 2. Use .NET Framework ADOMD Assemblies

Instead of the default `net8.0` version, use `net472` (or `net48`) which is compatible with pythonnet on Windows:

```python
# In NuGet package discovery, prefer .NET Framework versions
preferred_tfm = (
    "net472",      # .NET Framework 4.7.2 - BEST for pythonnet on Windows
    "net48",       # .NET Framework 4.8
    "netstandard2.0",
    "net6.0",
    "net8.0",      # .NET Core - INCOMPATIBLE with pythonnet on Windows
)
```

### 3. Add ADOMD to PATH Early

Add the ADOMD directory to Windows PATH before importing clr:

```python
import os
import sys

def _setup_adomd_path_early():
    """Add ADOMD.NET directory to PATH before clr is imported."""
    base = os.path.expanduser("~/.nuget/packages/microsoft.analysisservices.adomdclient")
    # ... find latest version and net472 directory ...
    
    sys.path.insert(0, adomd_dir)
    os.environ['PATH'] = adomd_dir + os.pathsep + os.environ.get('PATH', '')
    return adomd_dir

# MUST be called before any 'import clr' statements
_setup_adomd_path_early()

# NOW safe to use pythonnet
import clr
from pyadomd import Pyadomd
```

### 4. Connection String Format

The successful connection format is simple password embedding:

```python
connection_string = (
    f"Provider=MSOLAP;"
    f"Data Source={xmla_endpoint};"
    f"Initial Catalog={catalog};"
    f"Password={token};"
    f"Persist Security Info=True;"
)
```

## Required Admin Approval

The tenant admin must grant consent for the Power BI public client to access datasets:

1. User initiates device code flow with Power BI scopes
2. Admin receives consent request in Azure Portal
3. Admin grants **Dataset.Read.All** (delegated permission) for the organization
4. Subsequent authentications work without additional prompts

## Complete Working Flow

1. **Early PATH Setup**: Add ADOMD net472 directory to PATH
2. **Import Dependencies**: Import clr, pythonnet, pyadomd
3. **MSAL Authentication**: Acquire token with device code flow
4. **Token Validation**: Verify token contains required scopes (optional but recommended)
5. **Connection**: Use simple password-based connection string
6. **Success**: XMLA connection established

## Key Learnings

### Why Azure CLI Failed
- Azure CLI only supports `user_impersonation` scope
- Cannot request Power BI dataset-specific scopes
- These scopes are required by XMLA endpoints

### Why DAX Studio Works
- Uses Microsoft first-party client
- Has pre-consented Power BI scopes
- No custom app registration needed
- Same permissions available via MSAL with public client

### Why pythonnet Had Issues
- .NET Core assemblies incompatible with .NET Framework runtime
- pythonnet on Windows uses .NET Framework by default
- Must use net472/net48 versions of ADOMD.NET
- Assembly path must be in PATH before runtime initialization

### Why Connection String Works
- Simple password embedding bypasses ADOMD's internal MSAL
- Token already has correct audience and scopes
- ADOMD validates token with Power BI service
- No need for ClaimsToken or complex auth schemes

## Troubleshooting

### "No module named 'Microsoft.AnalysisServices'"
- **Cause**: ADOMD directory not in PATH before clr import
- **Fix**: Ensure `_setup_adomd_path_early()` runs first

### "Could not load type 'System.MarshalByRefObject'"
- **Cause**: Using net8.0 assemblies with pythonnet
- **Fix**: Use net472 or net48 versions instead

### "Access token lacks Dataset/Model scopes"
- **Cause**: Token doesn't have required dataset permissions
- **Fix**: Use MSAL device flow with Power BI public client ID
- **Alternative**: Request admin consent for Dataset.Read.All

### Connection succeeds but shows warnings
- **Expected**: Script tries multiple connection formats
- **Result**: Final format succeeds despite earlier warnings
- **Improvement**: Can suppress warnings with verbose=False flag

## Files Modified

- `scripts/test_cli_xmla_connection.py`: Enhanced test script with MSAL support and .NET Framework compatibility
- `docs/XMLA_AUTH_NOTES.md`: Original notes with workspace-specific values
- `docs/XMLA_AUTH_SOLUTION.md`: This comprehensive solution document

## Testing

To test XMLA connection with MSAL:

```bash
python scripts/test_cli_xmla_connection.py \
    --xmla "powerbi://api.powerbi.com/v1.0/myorg/YourWorkspace" \
    --catalog "YourDataset" \
    --tenant "your-tenant-id" \
    --auth-mode msal
```

Expected output:
```
[ACTION] Complete the device code authentication to continue:
To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code XXXXXXXX to authenticate.
[INFO] Acquired token via MSAL (device code)
[OK] Connected via direct password embedding at 'powerbi://...' with MSAL (device code).
```

## References

- [Power BI XMLA Endpoint Documentation](https://learn.microsoft.com/en-us/power-bi/enterprise/service-premium-connect-tools)
- [MSAL Python Documentation](https://msal-python.readthedocs.io/)
- [pythonnet Documentation](https://pythonnet.github.io/)
- [ADOMD.NET Reference](https://learn.microsoft.com/en-us/analysis-services/adomd/developing-with-adomd-net)
