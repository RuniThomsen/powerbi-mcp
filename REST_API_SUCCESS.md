# Power BI REST Execute Queries - Live Test Results

**Date:** October 3, 2025  
**Status:** ✅ **SUCCESS**

## Summary

Successfully tested the Power BI Execute Queries REST API endpoint against the live CN_DEV workspace using Azure CLI authentication. The REST API works as an alternative to XMLA endpoints when admin-consented dataset scopes are not available.

## Environment

- **Workspace:** CN_DEV (`72c9e9ad-537d-42a3-aefb-09df64c999af`)
- **Dataset:** Model (`b8565a45-8864-4324-8d77-8d9aadec4dcc`)
- **Authentication:** Azure CLI (AzureCliCredential)
- **Tenant:** `17f69c66-2114-4826-9fb1-6e496607aebc`

## Test Results

### ✅ Test 1: Simple Table Query
**Command:**
```bash
python scripts/execute_queries.py \
  --workspace-id 72c9e9ad-537d-42a3-aefb-09df64c999af \
  --dataset-id b8565a45-8864-4324-8d77-8d9aadec4dcc \
  --query "EVALUATE TOPN(5, 'Date')"
```

**Result:** HTTP 200 - Successfully returned 5 rows from the Date table with 18 columns.

**Sample Output:**
```
Date[Date]           | Date[DateKey] | Date[FiscalYear] | Date[FiscalQuarter]
2020-07-02T00:00:00 | 20200702      | 2020             | Q2
2025-07-24T00:00:00 | 20250724      | 2025             | Q2
2020-07-30T00:00:00 | 20200730      | 2020             | Q2
2021-07-06T00:00:00 | 20210706      | 2021             | Q2
2025-07-29T00:00:00 | 20250729      | 2025             | Q2
```

### ✅ Test 2: Aggregation Query
**Command:**
```bash
python scripts/execute_queries.py \
  --workspace-id 72c9e9ad-537d-42a3-aefb-09df64c999af \
  --dataset-id b8565a45-8864-4324-8d77-8d9aadec4dcc \
  --query "EVALUATE SUMMARIZECOLUMNS('Date'[FiscalYear], \"RowCount\", COUNTROWS('Date'))"
```

**Result:** HTTP 200 - Successfully aggregated data by fiscal year.

**Output:**
```
Date[FiscalYear] | [RowCount]
2021             | 331
2023             | 335
2024             | 350
2025             | 181
2022             | 348
2019             | 89
2020             | 344
```

### ✅ Test 3: JSON Output
**Command:**
```bash
python scripts/execute_queries.py \
  --workspace-id 72c9e9ad-537d-42a3-aefb-09df64c999af \
  --dataset-id b8565a45-8864-4324-8d77-8d9aadec4dcc \
  --query "EVALUATE TOPN(10, 'Date')" \
  --output query_results.json
```

**Result:** HTTP 200 - Results saved to `query_results.json` for programmatic processing.

### ❌ Test 4: INFO Functions Not Supported
**Command:**
```bash
python scripts/execute_queries.py \
  --query "EVALUATE TOPN(5, INFO.TABLES())"
```

**Result:** HTTP 400 - Failed with "DatasetExecuteQueriesError"

**Finding:** The Execute Queries REST API only supports DAX queries. INFO functions (DMV queries like `INFO.TABLES()`, `INFO.MEASURES()`) are not supported via REST. These require XMLA endpoint access.

## Key Findings

### ✅ What Works
1. **Standard DAX queries** - `EVALUATE`, `TOPN`, table expressions
2. **Aggregations** - `SUMMARIZECOLUMNS`, `COUNTROWS`, `SUM`, etc.
3. **Azure CLI authentication** - No service principal needed for personal use
4. **JSON output** - Results can be saved for programmatic processing
5. **Column references** - Fully qualified column names work correctly

### ❌ What Doesn't Work
1. **INFO functions** - `INFO.TABLES()`, `INFO.MEASURES()`, `INFO.COLUMNS()`
2. **DMV queries** - Direct schema queries via system tables
3. **MDX queries** - Only DAX is supported
4. **Measure references** - Must reference actual measures in the model, not arbitrary DAX expressions

## Limitations

As documented in the Microsoft API:
- **One query per API call**
- **One table request per query**
- **Maximum 100,000 rows or 1,000,000 values** per query
- **Maximum 15MB** of data per query
- **120 query requests per minute per user**
- **Tenant setting required:** "Dataset Execute Queries REST API" must be enabled
- **No MDX support** - Only DAX queries

## Authentication Comparison

| Method | Scopes Required | Works with REST API? | Works with XMLA? |
|--------|----------------|---------------------|------------------|
| Azure CLI | `user_impersonation` | ✅ Yes | ❌ No (needs Dataset scopes) |
| Service Principal | App permissions | ✅ Yes | ✅ Yes |
| MSAL Device Flow | Power BI API scopes | ✅ Yes | ✅ Yes (with admin consent) |

## Recommendations

### For Current Situation (No Admin Consent)
Use the REST Execute Queries API via Azure CLI:
- ✅ No admin consent required
- ✅ Works immediately after `az login`
- ✅ Suitable for data queries and aggregations
- ❌ Cannot query schema/metadata (no INFO functions)
- ❌ Cannot use MDX queries

### For Full Functionality
Request admin consent for Dataset.Read.All scope:
- ✅ Enables XMLA endpoint access
- ✅ Supports INFO functions for schema discovery
- ✅ Supports MDX queries
- ✅ Better performance for complex queries
- ⚠️ Requires tenant admin approval

## Scripts Reference

- **Discovery:** `scripts/discover_workspace_info.py` - Find workspace and dataset IDs
- **Query Execution:** `scripts/execute_queries.py` - Execute DAX queries via REST API
- **Documentation:** `AZURE_CLI_ANALYSIS.md` - Full authentication analysis

## Next Steps

1. ✅ REST API validated and working
2. ⏭️ Use REST for data queries until XMLA access is granted
3. ⏭️ For metadata queries, request admin consent for Dataset.Read.All
4. ⏭️ Consider service principal for automated/production scenarios

---

**Conclusion:** The Power BI REST Execute Queries endpoint provides a viable alternative to XMLA for data queries when working with Azure CLI authentication and standard user permissions.
