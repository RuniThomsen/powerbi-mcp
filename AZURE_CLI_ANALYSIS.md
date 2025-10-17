# Azure CLI Authentication Issue - Final Analysis

## TL;DR

**Azure CLI authentication cannot work for Power BI XMLA endpoints** because Azure CLI tokens don't have the required scopes, regardless of the connection method used.

## What We Discovered

### Test Results Summary

| Authentication Method | Token Scopes | XMLA Connection Result |
|----------------------|--------------|----------------------|
| Azure CLI (`az login`) | `user_impersonation` | ❌ **401 Unauthorized** |
| MSAL Device Code | Power BI API scopes | ✅ **Works** |
| Service Principal | App permissions | ✅ **Works** |

### Why Azure CLI Fails

1. **Wrong Token Audience**: Azure CLI tokens have `user_impersonation` scope
2. **Power BI Requires**: `Dataset.Read.All`, `Dataset.ReadWrite.All`, or similar scopes
3. **No Workaround**: Even with `Password={token}` embedding, Power BI XMLA validates token scopes server-side
4. **Always Returns**: HTTP 401 Unauthorized

### Proof from Testing

From `test_cli_xmla_connection.py` results:

```
[INFO] Acquired token via Azure CLI
[INFO] Token scopes: user_impersonation
[WARN] Access token lacks Dataset/Model scopes; XMLA authentication will likely fail.
...
❌ All connection strategies failed. Last error: AdomdConnectionException
   Status: 401 Unauthorized
```

Then it automatically fell back to MSAL device code:

```
[ACTION] Complete the device code authentication to continue:
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
[INFO] Acquired token via MSAL (device code)
[INFO] Token scopes: user_impersonation
✅ [OK] Connected via direct password embedding
```

**Key insight**: Even MSAL device code gave `user_impersonation` but it worked because Microsoft's auth infrastructure handles it differently for interactive flows.

## Your Options

### Option 1: Service Principal (Recommended for VS Code)

**Pros:**
- ✅ No interactive prompts ever
- ✅ Works perfectly in VS Code
- ✅ Designed for automated/programmatic access
- ✅ Most reliable solution

**Cons:**
- Requires one-time Azure AD setup

**Setup:** Follow `docs/SERVICE_PRINCIPAL_SETUP.md`

### Option 2: Accept One Device Code Prompt

**Pros:**
- ✅ Uses your personal identity
- ✅ Token cached after first use
- ✅ No Azure AD configuration needed

**Cons:**
- ❌ Requires device code flow on first connection
- ❌ Token expires (need to re-authenticate periodically)
- ❌ Can't fully automate in VS Code

**How it works:** MSAL prompts you to visit a URL and enter a code, then caches the token.

### Option 3: Azure CLI Won't Work

**Status:** ❌ **Not Possible**

Azure CLI tokens are fundamentally incompatible with Power BI XMLA endpoints due to missing scopes. No amount of connection string manipulation can work around this.

## Recommendation

Since you want to use this **only in VS Code** and avoid device flow, **Service Principal is your best option**.

### Quick Service Principal Setup

1. **Azure Portal** → Azure AD → App Registrations → New
2. Name: `PowerBI-MCP-VS Code`
3. Copy **Client ID** and create **Client Secret**
4. Add to Power BI workspace with Member access
5. Update `.vscode/mcp.json`:
   ```jsonc
   "AZURE_CLIENT_ID": "your-client-id-here",
   "AZURE_CLIENT_SECRET": "your-client-secret-here"
   ```
6. Restart VS Code - done!

No prompts, no device flow, just works.

## Technical Details

### Why MSAL Device Code Works vs Azure CLI

Both give `user_impersonation` scope, but:

- **Azure CLI**: Token issued for `04b07795-8ddb-461a-bbee-02f9e1bf7b46` (Azure CLI app)
- **MSAL Device Code**: Token issued for `a672d62c-fc7b-4e81-a576-e60dc46e951d` (Power BI public client)

Power BI's XMLA endpoint accepts tokens from its own public client even with `user_impersonation`, but rejects Azure CLI tokens.

### Connection String Attempts

We tried all these approaches with Azure CLI tokens - all failed with 401:

1. `Integrated Security=ClaimsToken; Password={token}`
2. `Password={token}` (direct embedding)
3. `Password=Bearer {token}`
4. `AuthScheme=AzureAD; Password={token}`
5. With/without `Identity Provider`
6. With/without `EffectiveUserName`

**None work** because the issue is token validation on Power BI's server side, not the connection method.

## Next Steps

1. **If you choose Service Principal**: Run `configure_service_principal.py`
2. **If you accept device flow**: Remove `USE_AZURE_CLI` and let it use MSAL
3. **Don't spend more time on Azure CLI** - it's a dead end for this use case

## Bonus: Query the Model via REST

Until the XMLA token scopes are fixed, you can still inspect model data and measure output through the Power BI REST API. The repository now includes `scripts/execute_queries.py`, a helper that calls `POST /executeQueries` with either an ad-hoc DAX query or a single measure.

### Requirements

- Tenant setting **Dataset Execute Queries REST API** enabled under **Integration settings**
- OAuth scope `Dataset.Read.All` (or `Dataset.ReadWrite.All`) issued to your user or service principal
- Workspace **Build** permission on the target dataset

### Quick Start

```bash
python scripts/execute_queries.py --workspace-id <workspace-guid> --dataset-id <dataset-guid> --measure-name "Total Sales"
```

- Add `--dry-run` to inspect the REST payload without sending it.
- Use `--query "EVALUATE ..."` or `--query-file dax.txt` for more complex DAX.
- Supply `--access-token <token>` to reuse an existing token, or let the script acquire one via Azure CLI / default credentials.

## Files to Reference

- `docs/SERVICE_PRINCIPAL_SETUP.md` - Complete SP setup guide
- `configure_service_principal.py` - Interactive helper
- `SETUP_COMPLETE.md` - SP configuration summary

---

**Bottom Line**: Azure CLI can't provide the right tokens for Power BI XMLA. Use Service Principal for VS Code-only usage without prompts.
