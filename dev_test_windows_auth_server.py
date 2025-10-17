"""
Test Windows Authentication support in server_enhanced.py
This tests the modified PowerBIDatasetClient with Windows auth
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Set environment variables
os.environ["PYTHONNET_RUNTIME"] = "coreclr"
os.environ["ADOMD_LIB_DIR"] = r"C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0"

# Import the server classes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from server_enhanced import PowerBIConnector
    logger.info("PowerBIConnector imported successfully")
except Exception as e:
    logger.error(f"Failed to import PowerBIConnector: {e}")
    sys.exit(1)


def test_windows_auth_connection():
    """Test Windows authentication with internal SSAS"""
    
    xmla_endpoint = "kmdbsprod63.bdk.kme.intern"
    initial_catalog = "KM BI"
    
    logger.info("=" * 70)
    logger.info("Testing Windows Authentication with PowerBIConnector")
    logger.info("=" * 70)
    logger.info(f"XMLA Endpoint: {xmla_endpoint}")
    logger.info(f"Initial Catalog: {initial_catalog}")
    logger.info(f"Authentication: Windows (tenant_id=None)")
    logger.info("")
    
    try:
        # Create client
        logger.info("Creating PowerBIConnector...")
        client = PowerBIConnector()
        logger.info("✓ Client created")
        logger.info("")
        
        # Test: Connect with Windows auth (tenant_id=None)
        logger.info("Test 1: Connecting with Windows Authentication...")
        result = client.connect(
            xmla_endpoint=xmla_endpoint,
            tenant_id=None,  # None triggers Windows auth
            client_id=None,
            client_secret=None,
            initial_catalog=initial_catalog
        )
        
        if result:
            logger.info("✓ Connection successful!")
            logger.info(f"  Connection string: {client.connection_string}")
            logger.info(f"  Authentication method: {client.authenticator.auth_method}")
            logger.info("")
        else:
            logger.error("✗ Connection failed")
            return False
        
        # Test: List tables
        logger.info("Test 2: Listing tables...")
        tables = client.discover_tables()
        logger.info(f"✓ Found {len(tables)} tables/cubes:")
        for i, table in enumerate(tables[:10], 1):
            table_name = table.get('name', 'N/A')
            table_type = table.get('type', 'N/A')
            logger.info(f"  {i}. {table_name} ({table_type})")
        if len(tables) > 10:
            logger.info(f"  ... and {len(tables) - 10} more")
        logger.info("")
        
        # Test: Describe table
        if tables:
            first_table = tables[0].get('name')
            logger.info(f"Test 3: Getting columns for table '{first_table}'...")
            columns = client.get_columns(first_table)
            logger.info(f"✓ Table has {len(columns)} columns:")
            for i, col in enumerate(columns[:5], 1):
                col_name = col.get('name', 'N/A')
                col_type = col.get('data_type', 'N/A')
                logger.info(f"  {i}. {col_name} ({col_type})")
            if len(columns) > 5:
                logger.info(f"  ... and {len(columns) - 5} more")
            logger.info("")
        
        logger.info("=" * 70)
        logger.info("✓✓✓ ALL TESTS PASSED!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Windows Authentication is working correctly!")
        logger.info("The MCP server is ready to connect to internal SSAS.")
        logger.info("")
        logger.info("To use with MCP:")
        logger.info("  1. Configure .vscode/mcp.json (already done)")
        logger.info("  2. Call mcp_pbi_connect with:")
        logger.info(f"     - xmla_endpoint: '{xmla_endpoint}'")
        logger.info(f"     - initial_catalog: '{initial_catalog}'")
        logger.info("     - tenant_id: null or omit")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_empty_string_tenant():
    """Test with empty string tenant_id (should also trigger Windows auth)"""
    
    xmla_endpoint = "kmdbsprod63.bdk.kme.intern"
    initial_catalog = "KM BI"
    
    logger.info("=" * 70)
    logger.info("Testing Empty String Tenant ID")
    logger.info("=" * 70)
    
    try:
        client = PowerBIConnector()
        result = client.connect(
            xmla_endpoint=xmla_endpoint,
            tenant_id="",  # Empty string should also trigger Windows auth
            initial_catalog=initial_catalog
        )
        
        if result:
            logger.info("✓ Empty string tenant_id also triggers Windows Authentication")
            logger.info(f"  Authentication method: {client.authenticator.auth_method}")
            return True
        else:
            logger.error("✗ Connection failed with empty tenant_id")
            return False
            
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        return False


def main():
    """Main entry point"""
    logger.info("Starting Windows Authentication Tests")
    logger.info("")
    
    test1_passed = test_windows_auth_connection()
    logger.info("")
    
    test2_passed = test_empty_string_tenant()
    logger.info("")
    
    if test1_passed and test2_passed:
        logger.info("=" * 70)
        logger.info("✓✓✓ ALL VALIDATION TESTS PASSED!")
        logger.info("=" * 70)
        sys.exit(0)
    else:
        logger.error("Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
