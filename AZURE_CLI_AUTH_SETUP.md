# Azure CLI Authentication Setup for PowerBI MCP

This document explains how to set up Azure CLI authentication as an alternative to Service Principal authentication.

## Option 1: Azure CLI Authentication (Recommended if you don't have Portal access)

### Step 1: Install Azure CLI

Download and install Azure CLI from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

For Windows, you can also use:
```powershell
# Using PowerShell
Invoke-WebRequest -Uri https://aka.ms/installazurecliwindows -OutFile .\AzureCLI.msi; Start-Process msiexec.exe -Wait -ArgumentList '/I AzureCLI.msi /quiet'; rm .\AzureCLI.msi
```

Or install via Chocolatey:
```powershell
choco install azure-cli
```

### Step 2: Login to Azure

```bash
az login
```

This will open a browser window for authentication. After successful login, you'll see your subscriptions.

### Step 3: Set the correct subscription (if needed)

```bash
# List available subscriptions
az account list --output table

# Set the subscription containing your Power BI workspace
az account set --subscription "your-subscription-id-or-name"
```

### Step 4: Configure the enhanced server

Update your `.env` file:
```env
# Enable Azure CLI authentication
USE_AZURE_CLI=true

# Your existing settings
DEFAULT_TENANT_ID=17f69c66-2114-4826-9fb1-6e496607aebc
DEFAULT_WORKSPACE=CN_DEV
DEFAULT_MODEL=Model
ADOMD_LIB_DIR=C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0

# Optional: OpenAI for natural language queries
OPENAI_API_KEY=your-openai-key-here
```

### Step 5: Use the enhanced server

Replace your current server with the enhanced version:
```powershell
# Copy the enhanced server
Copy-Item "src/server_enhanced.py" "src/server.py"

# Start the server
python src/server.py
```

### Step 6: Connect using Azure CLI auth

When connecting, you only need to provide:
- `xmla_endpoint`
- `initial_catalog` 
- `tenant_id`

No `client_id` or `client_secret` needed!

## Option 2: Create Service Principal without Portal Access

If you prefer Service Principal authentication but don't have Portal access, you can create one using Azure CLI:

### Step 1: Install and login to Azure CLI (same as above)

### Step 2: Create Service Principal

```bash
# Create a new service principal
az ad sp create-for-rbac --name "powerbi-mcp-sp" --role "Contributor" --scopes "/subscriptions/your-subscription-id"
```

This will output:
```json
{
  "appId": "your-client-id",
  "displayName": "powerbi-mcp-sp",
  "password": "your-client-secret",
  "tenant": "your-tenant-id"
}
```

### Step 3: Grant Power BI permissions

```bash
# Get the service principal object ID
SP_OBJECT_ID=$(az ad sp show --id "your-client-id" --query "id" -o tsv)

# Grant Power BI Service Administrator role (if you have permissions)
# This requires Global Administrator or Privileged Role Administrator permissions
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/directoryRoles/roleTemplateId=Power BI Service Administrator/members" \
  --body "{\"@odata.id\": \"https://graph.microsoft.com/v1.0/directoryObjects/${SP_OBJECT_ID}\"}"
```

**Note:** The Power BI permissions step may fail if you don't have sufficient privileges. In that case, you'll need to ask an administrator to grant the service principal access to Power BI workspaces.

### Step 4: Update .env file

```env
# Service Principal authentication
DEFAULT_TENANT_ID=your-tenant-id
DEFAULT_CLIENT_ID=your-client-id
DEFAULT_CLIENT_SECRET=your-client-secret
DEFAULT_WORKSPACE=CN_DEV
DEFAULT_MODEL=Model
ADOMD_LIB_DIR=C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0
```

## Option 3: Alternative Authentication Methods

The enhanced server also supports:

1. **Managed Identity**: Automatic when running on Azure VMs, App Service, etc.
2. **DefaultAzureCredential**: Tries multiple auth methods in order:
   - Environment variables (for Service Principal)
   - Managed Identity  
   - Azure CLI
   - Visual Studio
   - VS Code Azure Account extension

## Troubleshooting

### Common Issues:

1. **"Azure CLI not logged in"**
   - Run `az login` again
   - Check `az account show` to verify login

2. **"Insufficient permissions"**
   - You need at least "Member" role in the Power BI workspace
   - For Service Principal, it needs to be added to the workspace

3. **"Token expired"**
   - Run `az login` again to refresh tokens

4. **"azure-identity not found"**
   - The enhanced server automatically installs this when needed
   - Or manually run: `pip install azure-identity`

### Verification Commands:

```bash
# Check Azure CLI login status
az account show

# Test Power BI access
az rest --method GET --url "https://api.powerbi.com/v1.0/myorg/groups"

# List your Power BI workspaces
az rest --method GET --url "https://api.powerbi.com/v1.0/myorg/groups" --query "value[].{name:name,id:id}" -o table
```

## Next Steps

1. Choose your preferred authentication method
2. Update your `.env` file accordingly  
3. Use the enhanced server (`server_enhanced.py`)
4. Test the connection with your Power BI workspace

The enhanced server provides better error messages and will tell you exactly which authentication method was used successfully.
