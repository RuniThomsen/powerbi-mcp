# XMLA Authentication Fix - October 2025

## Summary

Successfully resolved Power BI XMLA authentication issues by implementing MSAL device code flow and fixing .NET Framework compatibility with pythonnet on Windows.

## The Problem

Azure CLI authentication was failing to connect to Power BI XMLA endpoints despite DAX Studio working perfectly. Investigation revealed three root causes:

1. **Token Scopes**: Azure CLI only provides `user_impersonation`, not `Dataset.Read.All` required by XMLA
2. **Assembly Compatibility**: ADOMD.NET net8.0 assemblies use .NET Core types incompatible with pythonnet's .NET Framework runtime
3. **Loading Order**: pythonnet requires ADOMD assemblies in PATH before runtime initialization

## The Solution

### 1. MSAL Device Code Authentication
Use Power BI's public client ID (Power Query for Excel) for device code flow:
- Client ID: `a672d62c-fc7b-4e81-a576-e60dc46e951d`
- Scopes: `https://analysis.windows.net/powerbi/api/.default`
- Requires one-time admin consent for Dataset.Read.All

### 2. .NET Framework Assemblies
Changed ADOMD.NET version preference from net8.0 to net472:
- net472/net48 are compatible with pythonnet on Windows
- net8.0 causes "System.MarshalByRefObject not found" errors
- Changed in: `scripts/test_cli_xmla_connection.py`

### 3. Early PATH Setup
Add ADOMD directory to PATH before any `import clr` statements:
```python
def _setup_adomd_path_early():
    # Find net472 ADOMD directory
    # Add to sys.path and os.environ['PATH']
    
_setup_adomd_path_early()  # BEFORE import clr
```

## Testing

Confirmed working with:
```bash
python scripts/test_cli_xmla_connection.py \
    --xmla "powerbi://api.powerbi.com/v1.0/myorg/CN_DEV" \
    --catalog "Model" \
    --tenant "17f69c66-2114-4826-9fb1-6e496607aebc" \
    --auth-mode msal
```

Output:
```
[ACTION] Complete the device code authentication to continue:
To sign in, use a web browser...
[INFO] Acquired token via MSAL (device code)
[OK] Connected via direct password embedding at 'powerbi://...' with MSAL (device code).
```

## Files Changed

### Modified
- `scripts/test_cli_xmla_connection.py`
  - Added early PATH setup for ADOMD
  - Changed assembly preference to net472
  - Added MSAL device code flow
  - Cleaned up excessive warning output
  - Removed debug logging

### Added
- `docs/XMLA_AUTH_SOLUTION.md` - Comprehensive solution documentation
- Updated `CHANGELOG.md` - Detailed change tracking

### Removed
- `test_simple_import.py` - Temporary test file
- `test_pyadomd_load.py` - Temporary test file  
- `test_assembly_inspect.py` - Temporary test file

## Key Learnings

**Why DAX Studio Works:**
- Uses Microsoft first-party client with pre-consented scopes
- Has Dataset.Read.All built-in
- Same permissions now available via MSAL public client

**Why Azure CLI Fails:**
- Limited to user_impersonation scope
- Cannot request Power BI dataset scopes
- Not suitable for XMLA connections

**Why pythonnet Had Issues:**
- Windows pythonnet uses .NET Framework runtime
- .NET Core assemblies (net8.0) incompatible
- Must use .NET Framework assemblies (net472/net48)
- Assembly path must be in PATH early

## Next Steps

The test script (`test_cli_xmla_connection.py`) now:
- ✅ Works with MSAL device code authentication
- ✅ Compatible with pythonnet on Windows
- ✅ Produces clean output
- ✅ Validates token scopes
- ✅ Properly documented

Server integration (`src/server_enhanced.py`) can now:
- Use the same MSAL flow for authentication
- Apply the same .NET Framework compatibility fixes
- Leverage the working connection patterns

## References

- Full documentation: `docs/XMLA_AUTH_SOLUTION.md`
- Original notes: `docs/XMLA_AUTH_NOTES.md`
- Test script: `scripts/test_cli_xmla_connection.py`
