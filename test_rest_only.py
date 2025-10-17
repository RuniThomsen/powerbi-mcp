#!/usr/bin/env python3
"""
Test Power BI REST API without XMLA connection
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from server_enhanced import AzureAuthenticator, PowerBIConnector
from powerbi_rest_client import PowerBIRestClient


def main():
    print("=" * 60)
    print("Testing Power BI REST API (No XMLA)")
    print("=" * 60)
    print()
    
    # Create minimal connector for auth only
    print("1. Setting up authentication...")
    connector = PowerBIConnector()
    connector._tenant_id = "17f69c66-2114-4826-9fb1-6e496607aebc"
    connector._client_id = None
    connector._client_secret = None
    
    # Mark as "connected" to bypass connection check
    connector.connected = True
    
    print("2. Creating REST API client...")
    rest_client = PowerBIRestClient(connector, connector.authenticator)
    
    # Test listing workspaces
    print()
    print("3. Listing Power BI workspaces via REST API...")
    try:
        result = rest_client.list_workspaces(top=20)
        workspaces = result.get("items", [])
        
        print(f"✅ Found {len(workspaces)} workspaces:")
        print()
        for i, ws in enumerate(workspaces, 1):
            ws_name = ws.get('name', 'Unknown')
            ws_id = ws.get('id', 'N/A')
            ws_type = ws.get('type', 'Workspace')
            is_dedicated = ws.get('isOnDedicatedCapacity', False)
            capacity = "Premium" if is_dedicated else "Shared"
            print(f"   {i:2d}. {ws_name}")
            print(f"       ID: {ws_id}")
            print(f"       Type: {ws_type} ({capacity})")
            print()
            
    except Exception as e:
        print(f"❌ Failed to list workspaces: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Test listing datasets
    if workspaces:
        print()
        print("4. Listing datasets in first workspace...")
        first_ws_id = workspaces[0].get("id")
        first_ws_name = workspaces[0].get("name")
        print(f"   Workspace: {first_ws_name}")
        print()
        
        try:
            result = rest_client.list_datasets(workspace_id=first_ws_id, top=10)
            datasets = result.get("items", [])
            
            if datasets:
                print(f"✅ Found {len(datasets)} datasets:")
                print()
                for i, ds in enumerate(datasets, 1):
                    ds_name = ds.get('name', 'Unknown')
                    ds_id = ds.get('id', 'N/A')
                    configured_by = ds.get('configuredBy', 'N/A')
                    is_refreshable = ds.get('isRefreshable', False)
                    print(f"   {i:2d}. {ds_name}")
                    print(f"       ID: {ds_id}")
                    print(f"       Configured by: {configured_by}")
                    print(f"       Refreshable: {'Yes' if is_refreshable else 'No'}")
                    print()
            else:
                print("⚠️  No datasets found in this workspace")
                
        except Exception as e:
            print(f"❌ Failed to list datasets: {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("=" * 60)
    print("✅ REST API test completed successfully!")
    print("=" * 60)
    print()
    print("Note: This test bypasses XMLA/ADOMD and uses pure REST API calls.")
    print("The REST API tools work independently of XMLA connection status.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
