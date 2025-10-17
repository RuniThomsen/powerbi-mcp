"""
Test Windows authentication through MCP server (stdio mode)
This simulates what VS Code's MCP integration would do
"""

import json
import subprocess
import sys
import os

def send_request(proc, request):
    """Send a JSON-RPC request to the server"""
    message = json.dumps(request) + "\n"
    proc.stdin.write(message)
    proc.stdin.flush()

def read_response(proc):
    """Read a JSON-RPC response from the server"""
    line = proc.stdout.readline()
    if line:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            print(f"Non-JSON output: {line.strip()}")
            return None
    return None

def test_windows_auth():
    """Test Windows authentication through MCP"""
    
    print("Starting MCP server in stdio mode...")
    print("(Check stderr output below for server initialization messages)\n")
    
    # Start the server
    env = os.environ.copy()
    env["PYTHONNET_RUNTIME"] = "coreclr"
    env["ADOMD_LIB_DIR"] = r"C:\Users\r.thomsen\.nuget\packages\microsoft.analysisservices.adomdclient\19.103.2\lib\net8.0"
    
    proc = subprocess.Popen(
        [
            r"d:\repos\powerbi-mcp\.venv\Scripts\python.exe",
            "-u",
            r"d:\repos\powerbi-mcp\src\server_enhanced.py"
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Merge stderr into stdout so we can see errors
        env=env,
        text=True,
        bufsize=1
    )
    
    try:
        print("Sending initialize request...")
        send_request(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        })
        
        response = read_response(proc)
        print(f"Initialize response: {json.dumps(response, indent=2)}")
        
        print("\nSending tools/list request...")
        send_request(proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        
        response = read_response(proc)
        if response:
            tools = response.get("result", {}).get("tools", [])
            print(f"Found {len(tools)} tools")
            if len(tools) == 0:
                print("WARNING: No tools found - server may not be fully initialized")
                print(f"Full response: {json.dumps(response, indent=2)}")
            else:
                connect_tool = next((t for t in tools if "connect" in t["name"]), None)
                if connect_tool:
                    print(f"Found connect tool: {connect_tool['name']}")
                    print(f"  Required params: {connect_tool['inputSchema'].get('required', [])}")
        
        print("\nSending pbi_connect request with Windows auth...")
        send_request(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "pbi_connect",
                "arguments": {
                    "xmla_endpoint": "kmdbsprod63.bdk.kme.intern",
                    "initial_catalog": "KM BI"
                    # No tenant_id, client_id, client_secret = Windows auth
                }
            }
        })
        
        response = read_response(proc)
        print(f"Connect response: {json.dumps(response, indent=2)}")
        
        if response and not response.get("error"):
            print("\nSUCCESS! Windows authentication works!")
            return True
        else:
            print("\nConnection failed")
            if response:
                print(f"Error: {response.get('error', 'Unknown error')}")
            return False
        
    except Exception as e:
        print(f"\nException during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            pass

if __name__ == "__main__":
    try:
        success = test_windows_auth()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
