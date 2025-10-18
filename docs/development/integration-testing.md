# Integration Testing Guide

This document describes how to set up and run integration tests for the Power BI MCP Server.

## Overview

Integration tests verify that the Power BI MCP Server works correctly with real Power BI datasets. These tests are disabled by default to prevent accidental API usage and require explicit configuration.

## Test Categories

### Unit Tests (Always Enabled)
- Connection logic validation
- DAX query parsing
- MCP protocol handling
- Error handling
- Mocking external dependencies

### Integration Tests (Optional)
- Real Power BI dataset connection
- Live XMLA endpoint communication
- Actual DAX query execution
- OpenAI API integration
- End-to-end MCP tool functionality

## Setup Instructions

### 1. Prerequisites

- Access to a Power BI workspace
- Service Principal with dataset permissions
- Test dataset with known structure
- OpenAI API key (optional, for AI features)

### 2. Test Dataset Preparation

Create or identify a test dataset with:
- At least one data table
- Known column names
- Predictable data for validation
- Measures (optional)

**Recommended test dataset structure:**
```
Sales Table:
- Date (DateTime)
- Product (Text)
- Category (Text)
- Amount (Decimal)
- Quantity (Integer)

Product Table:
- ProductID (Integer)
- ProductName (Text)
- Category (Text)
```

### 3. Service Principal Setup

1. **Create Service Principal** in Azure Portal
2. **Grant Power BI access**:
   - Add to workspace as Member or Admin
   - Enable Service Principal access in tenant settings
3. **Note credentials**:
   - Tenant ID
   - Client ID  
   - Client Secret

### 4. Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Enable integration tests
ENABLE_INTEGRATION_TESTS=true

# Test dataset connection
TEST_XMLA_ENDPOINT=powerbi://api.powerbi.com/v1.0/myorg/TestWorkspace
TEST_TENANT_ID=your-tenant-id
TEST_CLIENT_ID=your-client-id
TEST_CLIENT_SECRET=your-client-secret
TEST_INITIAL_CATALOG=TestDataset

# Test validation settings
TEST_EXPECTED_TABLE=Sales
TEST_EXPECTED_COLUMN=Amount
TEST_DAX_QUERY=EVALUATE TOPN(1, Sales)
TEST_MIN_TABLES_COUNT=2

# OpenAI for AI features (optional)
OPENAI_API_KEY=your-openai-key
```

## Running Tests

### Interactive Mode (Recommended)

```bash
# Interactive runner with safety confirmations
python run_integration_tests.py
```

This will:
- Check configuration
- Display test settings
- Ask for confirmation before running
- Show detailed progress

### Direct Pytest

```bash
# Run integration tests directly
python -m pytest tests/test_integration.py -v

# Run specific test class
python -m pytest tests/test_integration.py::TestPowerBIIntegration -v

# Run with detailed output
python -m pytest tests/test_integration.py -v -s --tb=long
```

### Using Makefile

```bash
# Run with confirmation
make test-integration

# Run without confirmation (CI/CD)
make test-integration-ci

# Check configuration
make check-integration-config
```

## Test Details

### PowerBIConnector Tests

- **Connection**: Validates XMLA endpoint connectivity
- **Table Discovery**: Tests table enumeration and filtering
- **Schema Retrieval**: Validates table structure extraction
- **DAX Execution**: Tests query execution and result parsing
- **Sample Data**: Validates data retrieval functionality

### DataAnalyzer Tests (OpenAI Required)

- **DAX Generation**: Tests natural language to DAX conversion
- **Result Interpretation**: Validates AI-powered result analysis
- **Question Suggestions**: Tests smart question generation

### MCP Server Tests

- **Tool Registration**: Validates MCP tool definitions
- **Tool Execution**: Tests end-to-end tool functionality
- **Error Handling**: Validates error responses
- **State Management**: Tests connection state handling

## Expected Test Results

### Successful Run Example

```
Power BI MCP Integration Tests
==============================
✅ Integration tests are ENABLED
✅ Required configuration found
✅ OpenAI API key found - AI features will be tested

Test Configuration:
  Dataset: SalesTestDataset
  Endpoint: powerbi://api.powerbi.com/v1.0/myorg/TestWorkspace
  Expected Table: Sales
  Min Tables: 2

Running integration tests...
==============================

tests/test_integration.py::TestPowerBIIntegration::test_connection_establishment PASSED
tests/test_integration.py::TestPowerBIIntegration::test_discover_tables PASSED
tests/test_integration.py::TestPowerBIIntegration::test_expected_table_exists PASSED
tests/test_integration.py::TestPowerBIIntegration::test_get_table_schema PASSED
tests/test_integration.py::TestPowerBIIntegration::test_execute_simple_dax_query PASSED
tests/test_integration.py::TestDataAnalyzerIntegration::test_generate_dax_query PASSED
tests/test_integration.py::TestMCPServerIntegration::test_connect_powerbi_tool PASSED

=============================== 7 passed in 45.23s ===============================
```

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   ```
   Error: Connection failed: Authentication failed
   ```
   - Verify Service Principal credentials
   - Check workspace access permissions
   - Confirm tenant ID is correct

2. **Dataset Not Found**
   ```
   Error: Initial catalog 'TestDataset' not found
   ```
   - Verify dataset name (case-sensitive)
   - Check workspace name in XMLA endpoint
   - Ensure dataset is published and accessible

3. **Table/Column Not Found**
   ```
   AssertionError: Expected table 'Sales' not found
   ```
   - Update TEST_EXPECTED_TABLE in .env
   - Check dataset structure
   - Verify table names are correct

4. **OpenAI API Errors**
   ```
   Error: OpenAI API request failed
   ```
   - Verify API key is valid
   - Check API quota and billing
   - Ensure network connectivity

### Debug Mode

Enable verbose logging:

```bash
# Set debug logging
export LOG_LEVEL=DEBUG

# Run with detailed output
python -m pytest tests/test_integration.py -v -s --log-cli-level=DEBUG
```

### Test Data Validation

Verify your test dataset:

```python
# Quick validation script
python -c "
from dotenv import load_dotenv
import os
load_dotenv()
from src.server import PowerBIConnector

connector = PowerBIConnector()
connector.connect(
    os.getenv('TEST_XMLA_ENDPOINT'),
    os.getenv('TEST_TENANT_ID'),
    os.getenv('TEST_CLIENT_ID'),
    os.getenv('TEST_CLIENT_SECRET'),
    os.getenv('TEST_INITIAL_CATALOG')
)
print('Tables:', connector.discover_tables())
"
```

## CI/CD Integration

### GitHub Actions

Integration tests run automatically on:
- Push to master branch
- When secrets are configured

Required GitHub repository secrets:
- `ENABLE_INTEGRATION_TESTS=true`
- `TEST_XMLA_ENDPOINT`
- `TEST_TENANT_ID`
- `TEST_CLIENT_ID`
- `TEST_CLIENT_SECRET`
- `TEST_INITIAL_CATALOG`
- `OPENAI_API_KEY` (optional)

### Other CI Systems

Use environment variable injection:

```yaml
# Example GitLab CI
test-integration:
  script:
    - python run_integration_tests.py --yes
  variables:
    ENABLE_INTEGRATION_TESTS: "true"
    TEST_XMLA_ENDPOINT: $TEST_XMLA_ENDPOINT
    # ... other variables
  only:
    - master
```

## Security Considerations

### Secrets Management

- **Never commit credentials** to version control
- **Use environment variables** for all sensitive data
- **Rotate Service Principal secrets** regularly
- **Limit test dataset access** to minimum required

### Test Isolation

- **Use dedicated test workspace** separate from production
- **Use test-specific datasets** with sample data only
- **Monitor API usage** to prevent quota exhaustion
- **Clean up test resources** after testing

## Cost Optimization

### API Usage

- **Power BI XMLA**: Usually unlimited for Premium workspaces
- **OpenAI API**: ~$0.01-0.05 per test run with gpt-4o-mini
- **Azure AD**: Authentication calls are typically free

### Optimization Tips

- **Run integration tests sparingly** (not on every commit)
- **Use smaller test datasets** to reduce query time
- **Cache authentication tokens** when possible
- **Skip AI tests** if OpenAI budget is limited

## Contributing

When adding integration tests:

1. **Follow existing patterns** for test structure
2. **Add appropriate skip conditions** for missing configuration
3. **Include helpful error messages** for setup issues
4. **Update this documentation** with new test descriptions
5. **Test with minimal configuration** to ensure graceful degradation
