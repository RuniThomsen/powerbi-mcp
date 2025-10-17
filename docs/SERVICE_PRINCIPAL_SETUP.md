# Service Principal Setup for Power BI MCP (No Device Flow)

This guide shows you how to set up Service Principal authentication for the Power BI MCP server, eliminating the need for device code flow or interactive authentication.

## Why Service Principal?

- ✅ No interactive authentication prompts
- ✅ Works perfectly in VS Code
- ✅ No token scope issues
- ✅ Designed for automated/programmatic access
- ✅ More secure than storing user credentials

## Prerequisites

- Azure AD tenant access
- Permissions to create App Registrations in Azure AD
- Power BI workspace admin access
- Power BI Pro or Premium license

---

## Step 1: Create App Registration (Service Principal) in Azure AD

### Using Azure Portal

1. **Open Azure Portal**
   - Go to [https://portal.azure.com](https://portal.azure.com)
   - Sign in with your account

2. **Navigate to Azure Active Directory**
   - Search for "Azure Active Directory" in the top search bar
   - Click on it

3. **Create App Registration**
   - In the left menu, click **App registrations**
   - Click **+ New registration** at the top
   
4. **Configure the registration**
   ```
   Name: PowerBI-MCP-Service
   Supported account types: Accounts in this organizational directory only
   Redirect URI: Leave blank (not needed for service principal)
   ```
   - Click **Register**

5. **Note down important values**
   
   After registration, you'll see an overview page. **Copy these values:**
   
   - **Application (client) ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   - **Directory (tenant) ID**: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
   
   Save these for later!

6. **Create a Client Secret**
   - In the left menu, click **Certificates & secrets**
   - Click **+ New client secret**
   - Description: `PowerBI MCP Secret`
   - Expires: Choose your preference (recommend 24 months)
   - Click **Add**
   
   ⚠️ **IMPORTANT**: Copy the **Value** of the secret immediately! You won't be able to see it again.
   
   - **Client Secret Value**: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Using Azure CLI (Alternative)

```bash
# Login to Azure
az login --tenant YOUR_TENANT_ID

# Create the app registration
az ad app create --display-name "PowerBI-MCP-Service"

# Note the "appId" from the output - this is your CLIENT_ID

# Create a service principal for the app
az ad sp create --id YOUR_APP_ID

# Create a client secret
az ad app credential reset --id YOUR_APP_ID --years 2

# Note the "password" from the output - this is your CLIENT_SECRET
```

---

## Step 2: Grant Power BI API Permissions (Optional but Recommended)

1. **In the App Registration page**
   - Click **API permissions** in the left menu
   - Click **+ Add a permission**
   
2. **Add Power BI Service permissions**
   - Select **Power BI Service**
   - Select **Delegated permissions**
   - Check these permissions:
     - `Dataset.Read.All`
     - `Dataset.ReadWrite.All`
   - Click **Add permissions**

3. **Grant admin consent** (if required)
   - Click **Grant admin consent for [Your Organization]**
   - Click **Yes** to confirm

---

## Step 3: Add Service Principal to Power BI Workspace

Now you need to give your Service Principal access to your Power BI workspace.

### Using Power BI Service (Web)

1. **Open Power BI Service**
   - Go to [https://app.powerbi.com](https://app.powerbi.com)
   - Navigate to your workspace (e.g., "CN_DEV")

2. **Open Workspace Settings**
   - Click the **...** (more options) next to your workspace name
   - Click **Workspace access**

3. **Add Service Principal**
   - Click **Add**
   - In the search box, enter the **name** of your app registration: `PowerBI-MCP-Service`
   - Select it from the dropdown
   - Choose permission level: **Member** or **Admin**
   - Click **Add**

### Enable Service Principal for Power BI (Tenant Setting)

⚠️ **You may need Power BI admin rights for this step**

1. **Open Power BI Admin Portal**
   - Go to [https://app.powerbi.com](https://app.powerbi.com)
   - Click the gear icon ⚙️ (top right)
   - Click **Admin portal**

2. **Enable Service Principal Access**
   - Go to **Tenant settings**
   - Find **Developer settings**
   - Enable **Service principals can use Power BI APIs**
   - Apply to: **The entire organization** or **Specific security groups**
   - Click **Apply**

3. **Enable XMLA Endpoint** (Required for MCP)
   - Still in Tenant settings
   - Find **Capacity settings** → **XMLA Endpoint**
   - Set to **Read Write** or **Read Only**
   - Click **Apply**

---

## Step 4: Configure VS Code MCP with Service Principal

Now update your VS Code MCP configuration with the Service Principal credentials.

Edit `.vscode/mcp.json` and add these environment variables:

```jsonc
{
  "servers": {
    "powerbi-mcp": {
      "command": "${workspaceFolder}/.venv/Scripts/python.exe",
      "args": ["-u", "${workspaceFolder}/src/server_enhanced.py"],
      "cwd": "${workspaceFolder}",
      "env": {
        "PYTHONNET_RUNTIME": "coreclr",
        "ADOMD_LIB_DIR": "C:\\Users\\r.thomsen\\.nuget\\packages\\microsoft.analysisservices.adomdclient\\19.103.2\\lib\\net8.0",
        
        // Service Principal Credentials
        "AZURE_TENANT_ID": "YOUR_TENANT_ID_HERE",
        "AZURE_CLIENT_ID": "YOUR_CLIENT_ID_HERE",
        "AZURE_CLIENT_SECRET": "YOUR_CLIENT_SECRET_HERE",
        
        // Power BI Connection Details
        "POWERBI_WORKSPACE": "CN_DEV",
        "POWERBI_MODEL": "Model",
        "POWERBI_DATASOURCE": "pbiazure://api.powerbi.com",
        "POWERBI_INTERNAL_CATALOG": "sobe_wowvirtualserver-b8565a45-8864-4324-8d77-8d9aadec4dcc"
      }
    }
  }
}
```

**Replace these values:**
- `YOUR_TENANT_ID_HERE`: The Directory (tenant) ID from Step 1
- `YOUR_CLIENT_ID_HERE`: The Application (client) ID from Step 1
- `YOUR_CLIENT_SECRET_HERE`: The client secret value from Step 1
- Update `ADOMD_LIB_DIR` to match your actual path (if different)

---

## Step 5: Test the Connection

Create a simple test script to verify everything works:

```python
# test_service_principal.py
import os
os.environ['PYTHONNET_RUNTIME'] = 'coreclr'
os.environ['ADOMD_LIB_DIR'] = r'C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0'

from src.server_enhanced import PowerBIConnector

connector = PowerBIConnector()
result = connector.connect(
    xmla_endpoint="powerbi://api.powerbi.com/v1.0/myorg/CN_DEV",
    tenant_id="YOUR_TENANT_ID",
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    initial_catalog="Model"
)

if result:
    print("✅ Connected successfully!")
    tables = connector.discover_tables()
    print(f"Found {len(tables)} tables")
else:
    print("❌ Connection failed")
```

Run the test:

```bash
.venv/Scripts/python.exe test_service_principal.py
```

---

## Troubleshooting

### Error: "Authentication failed"

**Check:**
1. Verify all three credentials (tenant_id, client_id, client_secret) are correct
2. Ensure the client secret hasn't expired
3. Check that Service Principal was added to the workspace

### Error: "The service principal is not authorized"

**Fix:**
1. Add the Service Principal to your Power BI workspace (Step 3)
2. Enable "Service principals can use Power BI APIs" in tenant settings
3. Wait a few minutes for permissions to propagate

### Error: "XMLA endpoint is not enabled"

**Fix:**
1. Go to Power BI Admin Portal
2. Enable XMLA Endpoint in tenant settings
3. Set to "Read Write" or "Read Only"

### Error: "Could not load ADOMD.NET"

**Fix:**
1. Run the ADOMD installation script:
   ```bash
   pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/install_dotnet_adomd.ps1
   ```
2. Update `ADOMD_LIB_DIR` in your MCP config

---

## Security Best Practices

1. **Never commit secrets to Git**
   - Add `.vscode/mcp.json` to `.gitignore` if it contains secrets
   - Or use environment variables instead

2. **Rotate client secrets regularly**
   - Set expiration dates on secrets
   - Create new secrets before old ones expire

3. **Use minimum required permissions**
   - Only grant "Member" access if "Admin" is not needed
   - Limit workspace access to specific workspaces

4. **Monitor Service Principal usage**
   - Check Azure AD sign-in logs
   - Review Power BI activity logs

---

## Next Steps

Once configured, you can use the MCP Power BI tools in VS Code:

1. Open VS Code
2. The MCP server will start automatically
3. Use Copilot Chat to interact with your Power BI data
4. No device flow or interactive prompts!

Example commands:
```
@workspace List all tables in my Power BI dataset
@workspace Query the Sales table
@workspace Show me the relationship between Products and Sales tables
```

---

## Alternative: Using .env File

If you prefer, you can also store credentials in a `.env` file instead of `mcp.json`:

```bash
# .env
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret

POWERBI_WORKSPACE=CN_DEV
POWERBI_MODEL=Model
```

Then in `mcp.json`, don't specify the credentials - the server will load them from `.env` automatically.
