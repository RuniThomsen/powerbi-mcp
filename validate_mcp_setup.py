#!/usr/bin/env python3
"""
Validate MCP Server Setup
Quick check to ensure everything is configured correctly
"""
import json
import os
import sys
from pathlib import Path


def main():
    print("=" * 70)
    print("Power BI MCP Server - Setup Validation")
    print("=" * 70)
    print()
    
    issues = []
    warnings = []
    
    # Check 1: Python environment
    print("1. Checking Python environment...")
    venv_python = Path(".venv/Scripts/python.exe")
    if venv_python.exists():
        print("   ✅ Virtual environment Python found")
    else:
        print("   ❌ Virtual environment Python not found")
        issues.append("Virtual environment not set up")
    
    # Check 2: MCP configuration files
    print("\n2. Checking MCP configuration files...")
    
    mcp_json = Path(".vscode/mcp.json")
    if mcp_json.exists():
        print("   ✅ .vscode/mcp.json exists")
        try:
            with open(mcp_json) as f:
                config = json.load(f)
                if "servers" in config and "powerbi-mcp" in config["servers"]:
                    print("   ✅ powerbi-mcp server configured")
                    server = config["servers"]["powerbi-mcp"]
                    if "--host" in server.get("args", []) or "--port" in server.get("args", []):
                        print("   ⚠️  Server configured with HTTP mode (should use stdio)")
                        warnings.append("mcp.json uses HTTP mode instead of stdio")
                    else:
                        print("   ✅ Server configured in stdio mode")
                else:
                    print("   ❌ powerbi-mcp server not found in configuration")
                    issues.append("MCP server not configured")
        except Exception as e:
            print(f"   ❌ Error reading mcp.json: {e}")
            issues.append("Invalid mcp.json")
    else:
        print("   ❌ .vscode/mcp.json not found")
        issues.append("mcp.json missing")
    
    settings_json = Path(".vscode/settings.json")
    if settings_json.exists():
        print("   ✅ .vscode/settings.json exists")
        try:
            with open(settings_json) as f:
                settings = json.load(f)
                copilot_mcp = settings.get("github.copilot.chat.experimental.mcpServers", {})
                if "powerbi-mcp" in copilot_mcp:
                    print("   ✅ Copilot MCP integration configured")
                    server = copilot_mcp["powerbi-mcp"]
                    if "--host" in server.get("args", []) or "--port" in server.get("args", []):
                        print("   ⚠️  Copilot server configured with HTTP mode (should use stdio)")
                        warnings.append("settings.json uses HTTP mode instead of stdio")
                    else:
                        print("   ✅ Copilot server configured in stdio mode")
                else:
                    print("   ⚠️  Copilot MCP integration not configured")
                    warnings.append("Copilot MCP not in settings.json")
        except Exception as e:
            print(f"   ⚠️  Error reading settings.json: {e}")
            warnings.append("Invalid settings.json")
    else:
        print("   ⚠️  .vscode/settings.json not found")
        warnings.append("settings.json missing")
    
    # Check 3: Server file
    print("\n3. Checking server files...")
    server_file = Path("src/server_enhanced.py")
    if server_file.exists():
        print("   ✅ src/server_enhanced.py exists")
    else:
        print("   ❌ src/server_enhanced.py not found")
        issues.append("Server file missing")
    
    rest_client = Path("src/powerbi_rest_client.py")
    if rest_client.exists():
        print("   ✅ src/powerbi_rest_client.py exists")
    else:
        print("   ❌ src/powerbi_rest_client.py not found")
        issues.append("REST client missing")
    
    # Check 4: Environment variables
    print("\n4. Checking environment variables...")
    adomd_lib = os.getenv("ADOMD_LIB_DIR")
    if adomd_lib:
        print(f"   ✅ ADOMD_LIB_DIR: {adomd_lib[:50]}...")
    else:
        print("   ⚠️  ADOMD_LIB_DIR not set (will use from config)")
        warnings.append("ADOMD_LIB_DIR not in environment")
    
    use_cli = os.getenv("USE_AZURE_CLI")
    if use_cli:
        print(f"   ✅ USE_AZURE_CLI: {use_cli}")
    else:
        print("   ⚠️  USE_AZURE_CLI not set (will use from config)")
        warnings.append("USE_AZURE_CLI not in environment")
    
    # Check 5: Azure CLI
    print("\n5. Checking Azure CLI...")
    try:
        import subprocess
        result = subprocess.run(["az", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("   ✅ Azure CLI installed")
            # Check login status
            result = subprocess.run(["az", "account", "show"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("   ✅ Azure CLI logged in")
            else:
                print("   ⚠️  Azure CLI not logged in - run 'az login'")
                warnings.append("Azure CLI not logged in")
        else:
            print("   ❌ Azure CLI not working")
            issues.append("Azure CLI not installed or not in PATH")
    except Exception as e:
        print(f"   ❌ Azure CLI check failed: {e}")
        issues.append("Azure CLI not available")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    
    if not issues and not warnings:
        print("✅ All checks passed! MCP server is properly configured.")
        print()
        print("Next steps:")
        print("  1. Reload VS Code window (Ctrl+Shift+P > Developer: Reload Window)")
        print("  2. Open Copilot Chat and ask about Power BI data")
        print("  3. Or run: python test_rest_only.py")
        return 0
    
    if issues:
        print(f"\n❌ Found {len(issues)} critical issues:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    
    if warnings:
        print(f"\n⚠️  Found {len(warnings)} warnings:")
        for i, warning in enumerate(warnings, 1):
            print(f"   {i}. {warning}")
    
    if not issues:
        print("\n✅ No critical issues - server should work with minor adjustments")
        return 0
    else:
        print("\n❌ Critical issues found - please fix before using MCP server")
        return 1


if __name__ == "__main__":
    sys.exit(main())
