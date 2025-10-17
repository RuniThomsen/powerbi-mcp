"""
Development script to test connection to internal SSAS server
Usage: python dev_test_internal_ssas.py
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Set environment variables for pythonnet
os.environ["PYTHONNET_RUNTIME"] = "coreclr"
os.environ["ADOMD_LIB_DIR"] = r"C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0"

try:
    import clr
    import pythonnet
    try:
        logger.info(f"pythonnet version: {pythonnet.__version__}")
    except AttributeError:
        logger.info("pythonnet loaded (version info not available)")
    
    # Load ADOMD.NET
    adomd_path = os.environ["ADOMD_LIB_DIR"]
    dll_path = os.path.join(adomd_path, "Microsoft.AnalysisServices.AdomdClient.dll")
    
    logger.info(f"Loading ADOMD from: {dll_path}")
    clr.AddReference(dll_path)
    
    from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand
    logger.info("ADOMD.NET loaded successfully!")
    
except Exception as e:
    logger.error(f"Failed to load ADOMD.NET: {e}")
    sys.exit(1)


def test_ssas_connection():
    """Test connection to internal SSAS server"""
    
    # Internal SSAS connection strings to try
    test_configs = [
        {
            "name": "HTTP Endpoint with Windows Auth",
            "connection_string": "Data Source=http://kmdbsprod63.bdk.kme.intern/;Integrated Security=SSPI;",
            "catalog": None  # Will need to specify database name
        },
        {
            "name": "Server Name with Windows Auth",
            "connection_string": "Data Source=kmdbsprod63.bdk.kme.intern;Integrated Security=SSPI;",
            "catalog": None
        },
        {
            "name": "HTTP with msmdpump.dll",
            "connection_string": "Data Source=http://kmdbsprod63.bdk.kme.intern/olap/msmdpump.dll;Integrated Security=SSPI;",
            "catalog": None
        }
    ]
    
    for config in test_configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {config['name']}")
        logger.info(f"Connection String: {config['connection_string']}")
        logger.info(f"{'='*60}")
        
        try:
            # Create connection
            conn = AdomdConnection(config['connection_string'])
            
            # Try to open connection
            logger.info("Opening connection...")
            conn.Open()
            
            logger.info(f"✓ Connection opened successfully!")
            logger.info(f"  Server Version: {conn.ServerVersion}")
            logger.info(f"  Database: {conn.Database}")
            
            # List available databases/catalogs
            logger.info("\nQuerying available databases...")
            cmd = conn.CreateCommand()
            cmd.CommandText = "SELECT [CATALOG_NAME] FROM $SYSTEM.DBSCHEMA_CATALOGS"
            
            reader = cmd.ExecuteReader()
            databases = []
            while reader.Read():
                db_name = reader.GetString(0)
                databases.append(db_name)
                logger.info(f"  - {db_name}")
            
            reader.Close()
            
            if databases:
                logger.info(f"\n✓ Found {len(databases)} database(s)")
                
                # Try to get cubes from first database
                if databases:
                    first_db = databases[0]
                    logger.info(f"\nQuerying cubes in '{first_db}'...")
                    
                    # Reconnect with specific database
                    conn.Close()
                    conn_with_db = AdomdConnection(
                        config['connection_string'] + f"Initial Catalog={first_db};"
                    )
                    conn_with_db.Open()
                    
                    cmd2 = conn_with_db.CreateCommand()
                    cmd2.CommandText = "SELECT [CUBE_NAME] FROM $SYSTEM.MDSCHEMA_CUBES WHERE [CUBE_SOURCE] = 1"
                    
                    reader2 = cmd2.ExecuteReader()
                    cubes = []
                    while reader2.Read():
                        cube_name = reader2.GetString(0)
                        cubes.append(cube_name)
                        logger.info(f"  - {cube_name}")
                    
                    reader2.Close()
                    conn_with_db.Close()
                    
                    logger.info(f"\n✓ Found {len(cubes)} cube(s) in '{first_db}'")
            
            conn.Close()
            logger.info(f"\n✓✓✓ SUCCESS! Connection works with: {config['name']}")
            return config  # Return successful config
            
        except Exception as e:
            logger.error(f"✗ Failed: {e}")
            logger.error(f"  Error type: {type(e).__name__}")
            continue
    
    logger.error("\n✗✗✗ All connection attempts failed")
    return None


def main():
    """Main entry point"""
    logger.info("Starting internal SSAS connection test...")
    logger.info(f"Target server: kmdbsprod63.bdk.kme.intern")
    logger.info(f"Authentication: Windows (Integrated Security)")
    
    result = test_ssas_connection()
    
    if result:
        logger.info("\n" + "="*60)
        logger.info("RECOMMENDED CONFIGURATION:")
        logger.info("="*60)
        logger.info(f"Connection String: {result['connection_string']}")
        logger.info("\nFor MCP configuration, use:")
        logger.info(f"  xmla_endpoint: {result['connection_string'].split('Data Source=')[1].split(';')[0]}")
        logger.info(f"  (You'll need to specify initial_catalog based on databases found above)")
    else:
        logger.error("\nNo successful connection. Please verify:")
        logger.error("  1. Server name is correct: kmdbsprod63.bdk.kme.intern")
        logger.error("  2. You have network access to the server")
        logger.error("  3. Windows authentication is configured on SSAS")
        logger.error("  4. Your Windows account has permissions on SSAS")


if __name__ == "__main__":
    main()
