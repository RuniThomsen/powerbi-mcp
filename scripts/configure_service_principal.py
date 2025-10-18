#!/usr/bin/env python3
"""
Interactive Service Principal Configuration Helper
This script helps you configure Service Principal authentication in VS Code MCP config.
"""
import json
import os
import sys
from pathlib import Path

def print_header():
    print("\n" + "=" * 70)
    print("  Power BI MCP - Service Principal Configuration Helper")
    print("=" * 70)
    print()

def print_step(num, title):
    print(f"\n{'─' * 70}")
    print(f"  Step {num}: {title}")
    print(f"{'─' * 70}\n")

def main():
    print_header()
    
    print("This script will help you configure Service Principal authentication")
    print("for your Power BI MCP server in VS Code.")
    print()
    print("Before running this, make sure you have:")
    print("  1. Created a Service Principal (App Registration) in Azure AD")
    print("  2. Added it to your Power BI workspace with appropriate permissions")
    print("  3. Have the CLIENT_ID and CLIENT_SECRET ready")
    print()
    
    response = input("Do you have these ready? (y/n): ").strip().lower()
    if response != 'y':
        print("\n📖 Please follow the setup guide first:")
        print("   📄 docs/SERVICE_PRINCIPAL_SETUP.md")
        print()
        print("   Or read the quick start:")
        print("   📄 SERVICE_PRINCIPAL_QUICKSTART.md")
        return
    
    print_step(1, "Collect Service Principal Credentials")
    
    print("Your tenant ID is already configured:")
    tenant_id = "17f69c66-2114-4826-9fb1-6e496607aebc"
    print(f"   Tenant ID: {tenant_id}")
    print()
    
    client_id = input("Enter your Application (Client) ID: ").strip()
    if not client_id:
        print("\n❌ Client ID is required!")
        return
    
    client_secret = input("Enter your Client Secret: ").strip()
    if not client_secret:
        print("\n❌ Client Secret is required!")
        return
    
    print()
    print("✅ Credentials collected:")
    print(f"   Tenant ID: {tenant_id}")
    print(f"   Client ID: {client_id[:8]}...{client_id[-4:]}")
    print(f"   Secret: {'*' * 32}")
    
    print_step(2, "Update VS Code MCP Configuration")
    
    mcp_config_path = Path(".vscode/mcp.json")
    
    if not mcp_config_path.exists():
        print(f"\n❌ ERROR: {mcp_config_path} not found!")
        print("   Are you running this from the repository root?")
        return
    
    # Read current config
    with open(mcp_config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove comments for JSON parsing
    lines = []
    for line in content.split('\n'):
        if '//' in line and not '"' in line.split('//')[0]:
            # Line starts with comment
            lines.append(line)
        else:
            lines.append(line)
    
    # Try to parse as JSON (ignoring comments)
    json_content = '\n'.join([l for l in lines if not l.strip().startswith('//')])
    try:
        config = json.loads(json_content)
    except json.JSONDecodeError:
        # If parsing fails, do string replacement
        print("   Using string replacement method...")
        updated = content.replace('YOUR_CLIENT_ID_HERE', client_id)
        updated = updated.replace('YOUR_CLIENT_SECRET_HERE', client_secret)
    else:
        # Update the config
        if 'servers' in config and 'powerbi-mcp' in config['servers']:
            env = config['servers']['powerbi-mcp'].get('env', {})
            env['AZURE_CLIENT_ID'] = client_id
            env['AZURE_CLIENT_SECRET'] = client_secret
            config['servers']['powerbi-mcp']['env'] = env
            
            # Write back with proper formatting
            updated = json.dumps(config, indent=2)
            # Restore comments manually
            updated = updated.replace(
                f'"AZURE_TENANT_ID": "{tenant_id}",',
                f'''// Service Principal Authentication (NO device flow!)
        // These are your actual Service Principal credentials
        "AZURE_TENANT_ID": "{tenant_id}",'''
            )
        else:
            print("\n❌ ERROR: Unexpected MCP config structure!")
            return
    
    # Backup original
    backup_path = mcp_config_path.with_suffix('.json.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"   ✅ Backed up original config to: {backup_path}")
    
    # Write updated config
    with open(mcp_config_path, 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f"   ✅ Updated: {mcp_config_path}")
    
    print_step(3, "Test the Configuration")
    
    print("Run the test script to verify everything works:")
    print()
    print("   .venv/Scripts/python.exe test_service_principal.py")
    print()
    
    test_now = input("Run test now? (y/n): ").strip().lower()
    if test_now == 'y':
        print("\n" + "─" * 70)
        os.environ['PYTHONNET_RUNTIME'] = 'coreclr'
        adomd_dir = r'C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0'
        os.environ['ADOMD_LIB_DIR'] = adomd_dir
        
        sys.path.insert(0, 'src')
        
        try:
            from server_enhanced import PowerBIConnector
            
            print("🔌 Testing connection...")
            connector = PowerBIConnector()
            result = connector.connect(
                xmla_endpoint="powerbi://api.powerbi.com/v1.0/myorg/CN_DEV",
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                initial_catalog="Model"
            )
            
            if result:
                print("✅ SUCCESS! Service Principal authentication works!")
                print(f"   Auth method: {connector.authenticator.auth_method}")
                
                tables = connector.discover_tables()
                print(f"   Found {len(tables)} tables")
                
                print()
                print("=" * 70)
                print("  🎉 All Done! Your Power BI MCP is ready to use!")
                print("=" * 70)
                print()
                print("Next steps:")
                print("  1. Restart VS Code")
                print("  2. The MCP server will start automatically")
                print("  3. Use Copilot Chat with your Power BI data")
                print("  4. No device flow prompts!")
                return
            else:
                print("❌ Connection test failed")
        except Exception as e:
            print(f"❌ Test failed: {e}")
            print()
            print("Troubleshooting:")
            print("  1. Verify Service Principal is added to workspace")
            print("  2. Check tenant settings allow Service Principals")
            print("  3. Ensure XMLA endpoint is enabled")
            print("  4. Wait a few minutes for permissions to propagate")
            return
    
    print()
    print("=" * 70)
    print("  Configuration Complete!")
    print("=" * 70)
    print()
    print("Final steps:")
    print("  1. Test manually: .venv/Scripts/python.exe test_service_principal.py")
    print("  2. Restart VS Code")
    print("  3. Start using your Power BI MCP tools!")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
