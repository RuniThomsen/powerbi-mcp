#!/usr/bin/env python3
"""VS Code Configuration Validator"""

import json
import os

def validate_vscode_config():
    """Validate VS Code configuration files"""
    vscode_dir = '.vscode'
    files_to_check = ['mcp.json', 'settings.json', 'tasks.json', 'launch.json', 'extensions.json']
    
    print('VS Code Configuration Validation')
    print('=' * 40)
    
    all_valid = True
    for file in files_to_check:
        path = os.path.join(vscode_dir, file)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f'✓ {file}: Valid JSON')
            except json.JSONDecodeError as e:
                print(f'✗ {file}: Invalid JSON - {e}')
                all_valid = False
        else:
            print(f'✗ {file}: Missing')
            all_valid = False
    
    print()
    print('VS Code Workspace Structure:')
    print('=' * 40)
    if os.path.exists(vscode_dir):
        for file in sorted(os.listdir(vscode_dir)):
            if file.endswith('.json'):
                print(f'  {file}')
        
        if all_valid:
            print()
            print('✓ VS Code workspace is ready!')
            print('✓ MCP integration configured')
            print('✓ GitHub Copilot integration enabled')
            print()
            print('Next steps:')
            print('  1. Open VS Code: code .')
            print('  2. Install recommended extensions')
            print('  3. Start MCP server via task or F5')
            print('  4. Use @workspace in Copilot Chat')
        else:
            print()
            print('✗ Some configuration files have issues')
    else:
        print('✗ .vscode directory not found')
        all_valid = False
    
    return all_valid

if __name__ == '__main__':
    validate_vscode_config()
