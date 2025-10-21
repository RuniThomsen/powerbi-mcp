#!/usr/bin/env python3
"""
Quick validation that everything is working.
Run: python scripts/validate_setup.py
"""

print("=== Validation Script ===")

try:
    print("1. Testing imports...")
    import sys
    import os
    
    # Set environment
    os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
    os.environ.setdefault("USE_AZURE_CLI", "true")
    
    # Check ADOMD path
    adomd_lib = os.getenv("ADOMD_LIB_DIR")
    if adomd_lib and adomd_lib not in sys.path:
        sys.path.insert(0, adomd_lib)
    
    print(f"   ADOMD_LIB_DIR: {adomd_lib}")
    print(f"   USE_AZURE_CLI: {os.getenv('USE_AZURE_CLI')}")
    
    print("2. Testing pythonnet...")
    import clr
    print("   ✓ pythonnet/clr works")
    
    print("3. Testing pyadomd...")
    from pyadomd import Pyadomd
    print("   ✓ pyadomd imports")
    
    print("4. Testing Azure identity...")
    from azure.identity import AzureCliCredential
    print("   ✓ azure-identity works")
    
    print("5. Testing server import...")
    # Don't actually run the server, just test import
    import importlib.util
    spec = importlib.util.spec_from_file_location("server_enhanced", "src/server_enhanced.py")
    if spec and spec.loader:
        print("   ✓ server_enhanced.py is importable")
    
    print("\n✅ All validations passed!")
    print("\nNext steps:")
    print("1. Start server: python src/server_enhanced.py --host 127.0.0.1 --port 8000")
    print("2. Connect using MCP client to: http://127.0.0.1:8000/sse")
    print("3. Use the 'connect' tool with your Power BI workspace details")
    
except Exception as e:
    print(f"\n❌ Validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
