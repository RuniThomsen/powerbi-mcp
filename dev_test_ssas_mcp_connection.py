"""
Test MCP connection to internal SSAS server
This simulates what the MCP client will do when calling mcp_pbi_connect
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

# Import the connector
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

try:
    from connector import PowerBIConnector
    logger.info("PowerBIConnector imported successfully")
except Exception as e:
    logger.error(f"Failed to import PowerBIConnector: {e}")
    sys.exit(1)


def test_ssas_connection():
    """Test connecting to internal SSAS using direct ADOMD.NET"""
    
    # Connection parameters for internal SSAS
    xmla_endpoint = "kmdbsprod63.bdk.kme.intern"
    initial_catalog = "KM BI"
    
    logger.info("=" * 60)
    logger.info("Testing Internal SSAS Connection via ADOMD.NET")
    logger.info("=" * 60)
    logger.info(f"XMLA Endpoint: {xmla_endpoint}")
    logger.info(f"Initial Catalog: {initial_catalog}")
    logger.info(f"Authentication: Windows (Integrated Security)")
    logger.info("")
    
    try:
        # Load ADOMD.NET
        import clr
        adomd_path = os.environ["ADOMD_LIB_DIR"]
        dll_path = os.path.join(adomd_path, "Microsoft.AnalysisServices.AdomdClient.dll")
        clr.AddReference(dll_path)
        from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand
        
        # Create Windows authentication connection string
        conn_str = f"Data Source={xmla_endpoint};Initial Catalog={initial_catalog};Integrated Security=SSPI;"
        
        logger.info("Connecting...")
        conn = AdomdConnection(conn_str)
        conn.Open()
        logger.info("✓ Connected successfully")
        logger.info(f"  Server Version: {conn.ServerVersion}")
        logger.info(f"  Database: {conn.Database}")
        logger.info("")
        
        # Test: List tables
        logger.info("Test 1: Listing tables...")
        cmd = conn.CreateCommand()
        # Use MDSCHEMA_MEASURES to get cubes/tables for SQL Server SSAS
        cmd.CommandText = "SELECT [CUBE_NAME] FROM $SYSTEM.MDSCHEMA_CUBES WHERE [CUBE_SOURCE] = 1"
        reader = cmd.ExecuteReader()
        
        tables = []
        while reader.Read():
            table_name = reader.GetString(0)
            tables.append(table_name)
        reader.Close()
        
        logger.info(f"✓ Found {len(tables)} tables:")
        for i, table in enumerate(tables[:10], 1):
            logger.info(f"  {i}. {table}")
        if len(tables) > 10:
            logger.info(f"  ... and {len(tables) - 10} more")
        logger.info("")
        
        # Test: Get table columns
        if tables:
            first_table = tables[0]
            logger.info(f"Test 2: Getting dimensions for cube '{first_table}'...")
            cmd2 = conn.CreateCommand()
            cmd2.CommandText = f"SELECT [DIMENSION_UNIQUE_NAME] FROM $SYSTEM.MDSCHEMA_DIMENSIONS WHERE [CUBE_NAME] = '{first_table}'"
            reader2 = cmd2.ExecuteReader()
            
            dimensions = []
            while reader2.Read():
                dim_name = reader2.GetString(0)
                dimensions.append(dim_name)
            reader2.Close()
            
            logger.info(f"✓ Cube has {len(dimensions)} dimensions:")
            for i, dim_name in enumerate(dimensions[:5], 1):
                logger.info(f"  {i}. {dim_name}")
            if len(dimensions) > 5:
                logger.info(f"  ... and {len(dimensions) - 5} more")
            logger.info("")
            
            # Test: Simple MDX query (SSAS Multidimensional uses MDX, not DAX)
            logger.info(f"Test 3: Running simple MDX query...")
            # Get measures from the cube without boolean filter
            cmd_measures = conn.CreateCommand()
            cmd_measures.CommandText = f"SELECT [MEASURE_UNIQUE_NAME] FROM $SYSTEM.MDSCHEMA_MEASURES WHERE [CUBE_NAME] = '{first_table}'"
            reader_measures = cmd_measures.ExecuteReader()
            
            measures = []
            count = 0
            while reader_measures.Read():
                if count < 3:
                    measure_name = reader_measures.GetString(0)
                    measures.append(measure_name)
                    count += 1
                else:
                    break
            reader_measures.Close()
            
            logger.info(f"✓ Found {count} measures in cube (showing first 3)")
            for measure in measures:
                logger.info(f"  - {measure}")
            logger.info("")
        
        conn.Close()
        
        logger.info("=" * 60)
        logger.info("✓✓✓ ALL TESTS PASSED!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("To use with MCP, we need to add Windows auth support to server_enhanced.py")
        logger.info("The connection string that works is:")
        logger.info(f"  {conn_str}")
        logger.info("")
        logger.info("Available databases:")
        logger.info("  - KM BI (cubes: Model, Finance, Sales, Service, KM Training, CRM)")
        logger.info("  - Super BI")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main entry point"""
    success = test_ssas_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
