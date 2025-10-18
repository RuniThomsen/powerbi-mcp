"""
Interactive script to connect and query internal SSAS server
Usage: python test_ssas_interactive.py
"""

import os
import sys

# Set environment
os.environ["PYTHONNET_RUNTIME"] = "coreclr"
os.environ["ADOMD_LIB_DIR"] = r"C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0"

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

print("=" * 70)
print("Internal SSAS Connection Test")
print("=" * 70)
print()

print("Loading modules...")
from server_enhanced import PowerBIConnector

print("Creating connector...")
connector = PowerBIConnector()

print()
print("Connecting to: kmdbsprod63.bdk.kme.intern")
print("Database: KM BI")
print("Auth: Windows (Integrated Security)")
print()

try:
    # Connect with Windows auth
    connector.connect(
        xmla_endpoint="kmdbsprod63.bdk.kme.intern",
        initial_catalog="KM BI"
    )
    
    print("✓ Connected successfully!")
    print()
    
    # List cubes
    print("=" * 70)
    print("Available Cubes:")
    print("=" * 70)
    tables = connector.discover_tables()
    for i, table in enumerate(tables, 1):
        print(f"{i}. {table.get('name', 'Unknown')}")
        if table.get('description'):
            print(f"   Description: {table['description']}")
    print()
    
    # Get details for first cube
    if tables:
        first_cube = tables[0].get('name')
        print("=" * 70)
        print(f"Details for '{first_cube}' cube:")
        print("=" * 70)
        
        details = connector.get_columns(first_cube)
        
        # Show dimensions (in SSAS Multidimensional, these come back as columns)
        print(f"Found {len(details)} dimensions/columns")
        print("\nFirst 10 dimensions:")
        for i, col in enumerate(details[:10], 1):
            col_name = col.get('name', 'Unknown')
            col_type = col.get('data_type', 'Unknown')
            print(f"  {i}. {col_name} ({col_type})")
        
        if len(details) > 10:
            print(f"  ... and {len(details) - 10} more")
        print()
    
    # Example query
    print("=" * 70)
    print("Running example MDX query:")
    print("=" * 70)
    
    mdx_query = """
    SELECT {[Measures].[SUMFinance Actual Amount DKK]} ON COLUMNS 
    FROM [Model]
    """
    
    print(f"Query: {mdx_query.strip()}")
    print()
    
    result = connector.query_data(mdx_query, max_rows=5)
    
    print(f"✓ Query executed successfully!")
    print(f"Columns: {result.get('columns', [])}")
    print(f"Row count: {result.get('row_count', 0)}")
    print()
    
    if result.get('rows'):
        print("Sample data:")
        for i, row in enumerate(result['rows'][:5], 1):
            print(f"  Row {i}: {row}")
    
    print()
    print("=" * 70)
    print("✓✓✓ All tests completed successfully!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Use the MCP tools in VS Code:")
    print("   - #mcp_ssas-internal_pbi_connect")
    print("   - #mcp_ssas-internal_pbi_list_tables")
    print("   - #mcp_ssas-internal_pbi_query_data")
    print()
    print("2. See SSAS_QUICK_START.md for examples")
    print()
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
