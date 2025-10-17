#!/usr/bin/env python3
"""
Development script to investigate the Product Hierarchy column binding issue.
This script will connect to the Power BI model and examine the metadata structure.
"""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from connector import PowerBIConnector
from dotenv import load_dotenv


def main():
    """Investigate the Product Hierarchy table structure and column bindings."""
    
    # Load environment variables
    load_dotenv()
    
    print("🔍 Investigating Product Hierarchy column binding issue...")
    print("=" * 60)
    
    # Initialize connector
    connector = PowerBIConnector()
    
    try:
        # Connect using environment settings
        xmla_endpoint = "powerbi://api.powerbi.com/v1.0/myorg/CN_DEV"
        initial_catalog = "Model"
        
        print(f"📡 Connecting to: {xmla_endpoint}")
        print(f"📊 Dataset: {initial_catalog}")
        
        connector.connect(
            xmla_endpoint=xmla_endpoint,
            initial_catalog=initial_catalog,
            tenant_id=os.getenv("AZURE_TENANT_ID"),
            use_azure_cli=True
        )
        
        print("✅ Connected successfully!")
        print()
        
        # Get all tables first
        print("📋 Available tables:")
        tables = connector.list_tables()
        for table in tables:
            print(f"  - {table['name']}")
        print()
        
        # Look for Product Hierarchy table specifically
        product_hierarchy_table = None
        for table in tables:
            if "Product Hierarchy" in table['name'] or "product hierarchy" in table['name'].lower():
                product_hierarchy_table = table
                break
        
        if product_hierarchy_table:
            print(f"🎯 Found Product Hierarchy table: {product_hierarchy_table['name']}")
            print()
            
            # Get detailed table information
            print("📊 Table Details:")
            table_details = connector.describe_table(product_hierarchy_table['name'])
            print(json.dumps(table_details, indent=2))
            print()
            
            # Look for the problematic column
            problematic_column = None
            for column in table_details.get('columns', []):
                if "Product Hierarchy Number" in column.get('name', '') or "number" in column.get('name', '').lower():
                    problematic_column = column
                    print(f"🔍 Found problematic column: {column}")
                    break
            
            if not problematic_column:
                print("⚠️  Could not find 'Product Hierarchy Number' column")
                print("Available columns:")
                for column in table_details.get('columns', []):
                    print(f"  - {column.get('name', 'Unknown')}: {column.get('dataType', 'Unknown')}")
            
        else:
            print("❌ Could not find Product Hierarchy table")
            print("Available tables:")
            for table in tables:
                print(f"  - {table['name']}")
        
        print()
        
        # Try to get schema information using DAX
        print("🔧 Attempting to get schema information via DAX...")
        try:
            # Query to get table schema information
            schema_query = """
            EVALUATE
            SELECTCOLUMNS(
                INFO.TABLES(),
                "TableName", [Name],
                "TableID", [ID]
            )
            """
            
            schema_result = connector.execute_dax(schema_query)
            print(f"📊 Found {len(schema_result)} tables in schema")
            
            # Look for Product Hierarchy in schema
            for row in schema_result:
                if "Product Hierarchy" in str(row.get('TableName', '')):
                    print(f"🎯 Schema entry: {row}")
            
        except Exception as e:
            print(f"⚠️  Could not retrieve schema via DAX: {e}")
        
        print()
        
        # Try to get column information for Product Hierarchy
        print("🔧 Attempting to get column information via DAX...")
        try:
            columns_query = """
            EVALUATE
            SELECTCOLUMNS(
                INFO.COLUMNS(),
                "TableName", [TableName],
                "ColumnName", [Name],
                "DataType", [DataType]
            )
            """
            
            columns_result = connector.execute_dax(columns_query)
            print(f"📊 Found {len(columns_result)} columns total")
            
            # Filter for Product Hierarchy columns
            product_hierarchy_columns = [
                row for row in columns_result
                if "Product Hierarchy" in str(row.get('TableName', ''))
            ]
            
            if product_hierarchy_columns:
                print("🎯 Product Hierarchy columns:")
                for col in product_hierarchy_columns:
                    print(f"  - {col.get('ColumnName', 'Unknown')}: {col.get('DataType', 'Unknown')}")
            else:
                print("❌ No Product Hierarchy columns found in schema")
                
        except Exception as e:
            print(f"⚠️  Could not retrieve columns via DAX: {e}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure you're logged in with 'az login'")
        print("2. Check that you have access to the CN_DEV workspace")
        print("3. Verify the Model dataset exists and is accessible")
        
    finally:
        if connector:
            connector.disconnect()
            print("🔌 Disconnected from Power BI")


if __name__ == "__main__":
    main()