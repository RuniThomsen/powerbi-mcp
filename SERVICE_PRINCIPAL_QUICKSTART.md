# 🎯 Service Principal Setup - Quick Start

## What We Did

We configured your Power BI MCP server to use **Service Principal authentication** instead of Azure CLI/device flow. This means:

- ✅ No more device code prompts
- ✅ No more "hanging" connections
- ✅ Works perfectly in VS Code
- ✅ More secure and reliable

## What You Need To Do

### 1. Create Service Principal (One-time setup)

Follow the detailed guide in `docs/SERVICE_PRINCIPAL_SETUP.md`:

**Quick version:**

1. **Go to Azure Portal** → Azure Active Directory → App registrations
2. **Create new registration**: Name it "PowerBI-MCP-Service"
3. **Copy these values:**
   - Application (client) ID
   - Directory (tenant) ID  
4. **Create client secret**: Certificates & secrets → New client secret
   - Copy the secret VALUE immediately!

5. **Add to Power BI workspace:**
   - Go to https://app.powerbi.com
   - Open your "CN_DEV" workspace
   - Workspace access → Add
   - Search for "PowerBI-MCP-Service"
   - Give it "Member" or "Admin" permission

6. **Enable in Power BI tenant** (may need admin):
   - Admin portal → Tenant settings
   - Enable "Service principals can use Power BI APIs"
   - Enable "XMLA Endpoint" (Read Write)

### 2. Update Your MCP Config

Your `.vscode/mcp.json` is already prepared! Just replace these placeholders:

```jsonc
"AZURE_CLIENT_ID": "YOUR_CLIENT_ID_HERE",       // ← Replace with your Client ID
"AZURE_CLIENT_SECRET": "YOUR_CLIENT_SECRET_HERE" // ← Replace with your Secret
```

The tenant ID is already set: `17f69c66-2114-4826-9fb1-6e496607aebc`

### 3. Test It

Run the test script to verify everything works:

```bash
.venv/Scripts/python.exe test_service_principal.py
```

This will:
- Prompt you for CLIENT_ID and CLIENT_SECRET
- Test the connection
- Show you all tables if successful

### 4. Use It in VS Code

Once the test passes:

1. Update `.vscode/mcp.json` with your real credentials
2. Restart VS Code
3. Use Copilot Chat to interact with Power BI:
   ```
   @workspace List all tables in my Power BI dataset
   @workspace Query the Sales table
   ```

## Files Created

- 📄 `docs/SERVICE_PRINCIPAL_SETUP.md` - Complete step-by-step guide
- 🧪 `test_service_principal.py` - Test script to verify authentication
- ⚙️ `.vscode/mcp.json` - Updated configuration (needs your credentials)

## Troubleshooting

### "Authentication failed"
- Double-check CLIENT_ID and CLIENT_SECRET are correct
- Verify the secret hasn't expired

### "The service principal is not authorized"
- Add Service Principal to your Power BI workspace (Step 1.5)
- Wait 5-10 minutes for permissions to propagate

### "XMLA endpoint is not enabled"
- Go to Power BI Admin Portal
- Tenant settings → Enable XMLA Endpoint

## Security Note

⚠️ **Never commit secrets to Git!**

Consider adding `.vscode/mcp.json` to `.gitignore` if it contains sensitive credentials, or use environment variables instead.

## Need Help?

1. Read the full guide: `docs/SERVICE_PRINCIPAL_SETUP.md`
2. Run the test script: `test_service_principal.py`
3. Check Azure AD and Power BI settings

---

**Once this is set up, your MCP Power BI tools will work smoothly in VS Code with no device flow prompts! 🚀**
