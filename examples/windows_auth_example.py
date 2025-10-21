"""
Quick test of Windows authentication without MCP protocol overhead
"""
import os
import sys

# Set environment
os.environ["PYTHONNET_RUNTIME"] = "coreclr"
os.environ["ADOMD_LIB_DIR"] = r"C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

print("Importing PowerBIConnector...")
from server_enhanced import PowerBIConnector

print("Creating connector...")
connector = PowerBIConnector()

print("\nTesting Windows Authentication...")
print("Connecting to: kmdbsprod63.bdk.kme.intern")
print("Database: KM BI")
print("Auth: Windows (Integrated Security)\n")

try:
    # Connect with Windows auth (no Azure AD params)
    result = connector.connect(
        xmla_endpoint="kmdbsprod63.bdk.kme.intern",
        initial_catalog="KM BI",
        tenant_id=None,  # Windows auth
        client_id=None,
        client_secret=None
    )
    
    if result:
        print("✓ Connection successful!")
        print(f"Connected: {connector.connected}")
        print(f"Connection string: {connector.connection_string[:100]}...")
        
        print("\nTesting table discovery...")
        tables = connector.discover_tables()
        print(f"✓ Found {len(tables)} tables/cubes")
        for table in tables[:5]:
            print(f"  - {table.get('name', 'Unknown')}")
        
        print("\n✓✓✓ Windows Authentication works perfectly!")
    else:
        print("✗ Connection failed")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
