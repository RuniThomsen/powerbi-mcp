"""
Simple test of Windows authentication with Pyadomd
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

def test_pyadomd_windows_auth():
    """Test Pyadomd with Windows authentication"""
    
    logger.info("Testing Pyadomd with Windows Authentication")
    logger.info("=" * 60)
    
    try:
        # Import pyadomd
        from pyadomd import Pyadomd
        logger.info("✓ Pyadomd imported successfully")
        
        # Test connection strings
        test_strings = [
            {
                "name": "With Provider prefix",
                "conn_str": "Provider=MSOLAP;Data Source=kmdbsprod63.bdk.kme.intern;Initial Catalog=KM BI;Integrated Security=SSPI;Connect Timeout=15;"
            },
            {
                "name": "Without Provider prefix",
                "conn_str": "Data Source=kmdbsprod63.bdk.kme.intern;Initial Catalog=KM BI;Integrated Security=SSPI;Connect Timeout=15;"
            }
        ]
        
        for test in test_strings:
            logger.info(f"\nTest: {test['name']}")
            logger.info(f"Connection string: {test['conn_str']}")
            
            try:
                logger.info("Creating Pyadomd connection...")
                with Pyadomd(test['conn_str']) as conn:
                    logger.info("✓ Connection opened successfully")
                    
                    # Try a simple query
                    cursor = conn.cursor()
                    cursor.execute("SELECT [CUBE_NAME] FROM $SYSTEM.MDSCHEMA_CUBES WHERE [CUBE_SOURCE] = 1")
                    rows = cursor.fetchall()
                    
                    logger.info(f"✓ Query executed, found {len(rows)} cubes")
                    for row in rows:
                        logger.info(f"  - {row[0]}")
                    
                    cursor.close()
                
                logger.info(f"✓✓✓ SUCCESS with: {test['name']}")
                return test['conn_str']
                
            except Exception as e:
                logger.error(f"✗ Failed: {e}")
                continue
        
        logger.error("All tests failed")
        return None
        
    except Exception as e:
        logger.error(f"Failed to import or test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def main():
    result = test_pyadomd_windows_auth()
    
    if result:
        logger.info("\n" + "=" * 60)
        logger.info("RECOMMENDED CONNECTION STRING:")
        logger.info(result)
    else:
        logger.error("\nNo successful connection")
    
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()
