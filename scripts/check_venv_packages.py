#!/usr/bin/env python3
"""Check virtual environment and required packages"""

import sys

def check_venv_and_packages():
    print('Python executable:', sys.executable)
    print('Virtual environment active:', hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
    
    # Check required packages
    packages = ['anyio', 'starlette', 'uvicorn', 'azure-identity', 'pyadomd', 'pythonnet']
    missing = []
    print('\nPackage Check:')
    print('=' * 30)
    
    for pkg in packages:
        try:
            __import__(pkg)
            print(f'✓ {pkg}')
        except ImportError:
            print(f'✗ {pkg} - MISSING')
            missing.append(pkg)
    
    if missing:
        print(f'\nMissing packages: {missing}')
        print('Run: pip install -r requirements.txt')
        return False
    else:
        print('\n✓ All required packages are installed')
        return True

if __name__ == '__main__':
    check_venv_and_packages()
