#!/usr/bin/env python3
"""
MCP Server installer and configuration helper for PowerBI MCP
"""
import json
import os
import platform
import shutil
from pathlib import Path

def get_claude_config_path():
    """Get the Claude Desktop configuration file path for current OS"""
    system = platform.system()
    
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    else:
        return None

def get_current_dir():
    """Get the absolute path to the current project directory"""
    return str(Path(__file__).parent.parent.absolute())

def install_claude_desktop():
    """Install PowerBI MCP server configuration for Claude Desktop"""
    config_path = get_claude_config_path()
    
    if not config_path:
        print("❌ Unsupported operating system for Claude Desktop auto-configuration")
        return False
    
    # Create config directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new one
    config = {}
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"⚠️  Could not read existing config: {e}")
            config = {}
    
    # Ensure mcpServers section exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Add PowerBI MCP server
    current_dir = get_current_dir()
    config["mcpServers"]["powerbi-mcp"] = {
        "command": "python",
        "args": [
            "src/server_enhanced.py",
            "--host", "127.0.0.1",
            "--port", "8000"
        ],
        "cwd": current_dir,
        "env": {
            "PYTHONNET_RUNTIME": "coreclr",
            "USE_AZURE_CLI": "true"
        }
    }
    
    # Write updated config
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ PowerBI MCP server installed to Claude Desktop")
        print(f"   Config file: {config_path}")
        print(f"   Project path: {current_dir}")
        print("\n📋 Next steps:")
        print("1. Restart Claude Desktop")
        print("2. Use the 'connect' tool to connect to your Power BI workspace")
        print("3. Example: Connect to workspace 'CN_DEV' with dataset 'Model'")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to write config: {e}")
        return False

def show_manual_setup():
    """Show manual setup instructions"""
    current_dir = get_current_dir()
    
    print("\n📋 Manual Setup Instructions")
    print("=" * 50)
    
    config = {
        "mcpServers": {
            "powerbi-mcp": {
                "command": "python",
                "args": [
                    "src/server_enhanced.py",
                    "--host", "127.0.0.1",
                    "--port", "8000"
                ],
                "cwd": current_dir,
                "env": {
                    "PYTHONNET_RUNTIME": "coreclr",
                    "USE_AZURE_CLI": "true"
                }
            }
        }
    }
    
    print("\n1. For Claude Desktop:")
    print("   Add this to your claude_desktop_config.json:")
    print("   " + json.dumps(config, indent=4).replace('\n', '\n   '))
    
    print(f"\n2. Config file locations:")
    print(f"   Windows: %APPDATA%\\Claude\\claude_desktop_config.json")
    print(f"   macOS: ~/Library/Application Support/Claude/claude_desktop_config.json")
    print(f"   Linux: ~/.config/Claude/claude_desktop_config.json")
    
    print(f"\n3. Project directory: {current_dir}")

def main():
    """Main installer function"""
    print("🚀 PowerBI MCP Server Configuration")
    print("=" * 40)
    
    current_dir = get_current_dir()
    print(f"Project location: {current_dir}")
    
    # Check if we're in the right directory
    server_file = Path(current_dir) / "src" / "server_enhanced.py"
    if not server_file.exists():
        print("❌ Error: server_enhanced.py not found!")
        print("   Make sure you're running this from the powerbi-mcp project root")
        return
    
    print("\nChoose installation method:")
    print("1. Auto-install for Claude Desktop")
    print("2. Show manual setup instructions")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        if install_claude_desktop():
            print("\n🎉 Installation complete!")
        else:
            print("\n❌ Auto-installation failed. Try manual setup.")
            show_manual_setup()
    elif choice == "2":
        show_manual_setup()
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
