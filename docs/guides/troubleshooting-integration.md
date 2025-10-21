# Power BI MCP Server - Known Issues & Solutions

This document describes common issues and their solutions when running Power BI MCP Server.

## ADOMD.NET Configuration Issues

### Problem: System.Configuration.ConfigurationManager Missing

**Error:**
```
System.IO.FileNotFoundException: Could not load file or assembly 'System.Configuration.ConfigurationManager'
```

**Root Cause:**
ADOMD.NET requires `System.Configuration.ConfigurationManager` which is not included by default in newer .NET versions.

**Solutions:**

#### Option 1: Install via NuGet (Recommended)
```bash
# Create a simple .NET project to manage dependencies
dotnet new console -n adomd-deps
cd adomd-deps
dotnet add package System.Configuration.ConfigurationManager
dotnet add package Microsoft.AnalysisServices.AdomdClient.NetCore.retail.amd64
dotnet restore
```

#### Option 2: Use Docker (Easiest)
The provided Docker container already includes all necessary dependencies:
```bash
docker build -t powerbi-mcp .
docker run -it --rm -e OPENAI_API_KEY=<key> powerbi-mcp
```

#### Option 3: Manual .NET Runtime Setup
1. Install .NET Runtime 8.0+
2. Download and install SQL Server Management Studio (includes ADOMD.NET)
3. Ensure `Microsoft.AnalysisServices.AdomdClient.dll` is in your PATH

### Problem: pythonnet Runtime Issues

**Error:**
```
Failed to set pythonnet runtime
```

**Solution:**
Set the correct runtime environment:
```bash
export PYTHONNET_RUNTIME=coreclr
export DOTNET_ROOT=/usr/share/dotnet  # Linux
# or
set PYTHONNET_RUNTIME=coreclr          # Windows
```

## Integration Test Environment Setup

### Problem: Tests Skip Due to Missing Dependencies

If you see:
```
❌ Integration tests are DISABLED
```

**Solution:**
1. Ensure ADOMD.NET is properly installed (see above)
2. Configure your `.env` file:
   ```bash
   ENABLE_INTEGRATION_TESTS=true
   TEST_XMLA_ENDPOINT=powerbi://api.powerbi.com/v1.0/myorg/YourWorkspace
   TEST_TENANT_ID=your-tenant-id
   TEST_CLIENT_ID=your-client-id
   TEST_CLIENT_SECRET=your-client-secret
   TEST_INITIAL_CATALOG=YourDataset
   ```

### Problem: Power BI Connection Authentication

**Error:**
```
Authentication failed
```

**Common Causes & Solutions:**

1. **Service Principal not granted access:**
   - Go to Power BI workspace settings
   - Add your Service Principal as Member or Admin
   - Enable "Service principals can use Power BI APIs" in tenant settings

2. **Incorrect credentials:**
   - Verify Tenant ID from Azure Portal → Azure Active Directory → Overview
   - Verify Client ID from Azure Portal → App Registrations → Your App
   - Generate new Client Secret if expired

3. **XMLA endpoint disabled:**
   - Go to Power BI Admin Portal
   - Enable "XMLA Endpoint" for your workspace type
   - Wait up to 1 hour for changes to take effect

### Problem: Dataset Not Found

**Error:**
```
Initial catalog 'DatasetName' not found
```

**Solution:**
1. Verify exact dataset name (case-sensitive)
2. Ensure dataset is published and not in Personal workspace
3. Check workspace name in XMLA endpoint URL
4. Verify Service Principal has access to the workspace

## Development Environment Issues

### Problem: Import Errors in Tests

**Error:**
```
ModuleNotFoundError: No module named 'pytest'
```

**Solution:**
```bash
pip install -r requirements.txt
# or specifically:
pip install pytest pytest-asyncio python-dotenv
```

### Problem: VS Code Python Interpreter

If imports fail in VS Code:
1. Press `Ctrl+Shift+P`
2. Type "Python: Select Interpreter"
3. Choose the Python environment where you installed dependencies

### Problem: Environment Variables Not Loading

**Error:**
```
Missing required environment variables
```

**Solution:**
1. Ensure `.env` file exists in project root
2. Check file permissions (should be readable)
3. Verify no extra spaces around variable names:
   ```bash
   # Good
   ENABLE_INTEGRATION_TESTS=true
   
   # Bad
   ENABLE_INTEGRATION_TESTS = true
   ```

## Performance Issues

### Problem: Slow Test Execution

**Causes:**
- Large datasets
- Network latency to Power BI
- Multiple authentication calls

**Solutions:**
1. **Use smaller test datasets:**
   ```bash
   TEST_MIN_TABLES_COUNT=1  # Instead of many tables
   ```

2. **Optimize test queries:**
   ```bash
   TEST_DAX_QUERY=EVALUATE TOPN(1, YourTable)  # Instead of full table
   ```

3. **Run tests selectively:**
   ```bash
   # Run only connection tests
   pytest tests/test_integration.py::TestPowerBIIntegration::test_connection_establishment -v
   ```

### Problem: API Rate Limits

**Error:**
```
TooManyRequests or rate limit exceeded
```

**Solution:**
1. Add delays between test runs
2. Use dedicated test workspace with fewer concurrent users
3. Run integration tests less frequently (not on every commit)

## CI/CD Issues

### Problem: GitHub Actions Secrets Not Working

**Error:**
```
Missing required environment variables in CI
```

**Solution:**
1. Go to GitHub repository → Settings → Secrets and variables → Actions
2. Add all required secrets:
   - `ENABLE_INTEGRATION_TESTS`
   - `TEST_XMLA_ENDPOINT`
   - `TEST_TENANT_ID`
   - `TEST_CLIENT_ID`
   - `TEST_CLIENT_SECRET`
   - `TEST_INITIAL_CATALOG`
   - `OPENAI_API_KEY` (optional)

### Problem: Docker Build Fails in CI

**Error:**
```
Failed to load ADOMD.NET
```

**Solution:**
Use the provided Dockerfile which includes all dependencies:
```yaml
# In your CI workflow
- name: Run integration tests
  run: |
    docker build -t powerbi-mcp-test .
    docker run --rm \
      -e ENABLE_INTEGRATION_TESTS=true \
      -e TEST_XMLA_ENDPOINT=${{ secrets.TEST_XMLA_ENDPOINT }} \
      powerbi-mcp-test python run_integration_tests.py --yes
```

## Debugging Tips

### Enable Debug Logging

Add to your `.env`:
```bash
LOG_LEVEL=DEBUG
DEBUG_MODE=true
```

### Test Individual Components

```bash
# Test only connection
python -c "
from src.server import PowerBIConnector
connector = PowerBIConnector()
# Test connection logic without real credentials
print('PowerBIConnector imported successfully')
"

# Test only ADOMD.NET loading
python -c "
import sys
sys.path.insert(0, 'src')
from server import Pyadomd
print('ADOMD.NET available' if Pyadomd else 'ADOMD.NET not available')
"
```

### Validate Environment

```bash
# Check all environment variables
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('Integration tests:', os.getenv('ENABLE_INTEGRATION_TESTS'))
print('XMLA endpoint:', 'Configured' if os.getenv('TEST_XMLA_ENDPOINT') else 'Missing')
print('OpenAI key:', 'Configured' if os.getenv('OPENAI_API_KEY') else 'Missing')
"
```

## Getting Help

If you encounter issues not covered here:

1. **Check existing issues:** [GitHub Issues](https://github.com/jpierzchala/powerbi-mcp/issues)
2. **Create new issue** with:
   - Error message (full stack trace)
   - Environment details (Python version, OS, .NET version)
   - Steps to reproduce
   - Your `.env` configuration (without sensitive values)

3. **Common information to include:**
   ```bash
   # Environment info
   python --version
   dotnet --version
   pip list | grep -E "(pytest|dotenv|openai|pyadomd|pythonnet)"
   
   # Test configuration (sanitized)
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Integration tests enabled:', os.getenv('ENABLE_INTEGRATION_TESTS')); print('Test endpoint configured:', bool(os.getenv('TEST_XMLA_ENDPOINT')))"
   ```
