# Using Internal SSAS with MCP Tools

This guide shows how to query your internal SSAS server `kmdbsprod63.bdk.kme.intern` using the MCP tools.

## Step 1: Connect to Internal SSAS

Use the `mcp_ssas-internal_pbi_connect` tool with Windows authentication:

```json
{
  "xmla_endpoint": "kmdbsprod63.bdk.kme.intern",
  "initial_catalog": "KM BI"
}
```

**Note:** By omitting `tenant_id`, `client_id`, and `client_secret`, the server automatically uses Windows Authentication (Integrated Security=SSPI).

## Step 2: List Available Cubes

After connecting, use `mcp_ssas-internal_pbi_list_tables` to see what's available:

```json
{}
```

This will show you the 6 cubes in the KM BI database:
- Model
- Finance
- Sales
- Service
- KM Training
- CRM

## Step 3: Get Cube Details

Use `mcp_ssas-internal_pbi_describe_table` to see dimensions in a cube:

```json
{
  "table_name": "Model"
}
```

This will show the 161 dimensions available in the Model cube.

## Step 4: Query Data

Use `mcp_ssas-internal_pbi_query_data` to run MDX queries:

### Example 1: Simple measure query

```json
{
  "query": "SELECT {[Measures].[SUMFinance Actual Amount DKK]} ON COLUMNS FROM [Model]",
  "max_rows": 10
}
```

### Example 2: Query with dimension

```json
{
  "query": "SELECT {[Measures].[Finance Actual Amount DKK YTD dynamic]} ON COLUMNS, [Account].Members ON ROWS FROM [Model]",
  "max_rows": 50
}
```

### Example 3: List dimension members

```json
{
  "query": "SELECT [Account].Members ON ROWS FROM [Model]",
  "max_rows": 100
}
```

## Important Notes

### MDX vs DAX
Your internal SSAS is **Multidimensional** (not Tabular), so you must use **MDX queries**, not DAX.

**MDX Format:**
```mdx
SELECT <columns> ON COLUMNS, <rows> ON ROWS FROM [CubeName]
```

**Common MDX Patterns:**
- `[Measures].[MeasureName]` - Access a measure
- `[Dimension].Members` - All members of a dimension
- `[Dimension].[Hierarchy].&[Key]` - Specific member
- `{item1, item2}` - Set of items
- `TOPN(n, set)` - Top N items

### REST API Not Available
The `pbi_rest_*` tools (like `pbi_rest_execute_query`, `pbi_rest_list_workspaces`) **only work with Power BI Service** (cloud).

For internal SSAS, use:
- ✅ `pbi_connect` - Connect with Windows auth
- ✅ `pbi_list_tables` - List cubes
- ✅ `pbi_describe_table` - Get cube details
- ✅ `pbi_query_data` - Run MDX queries
- ❌ `pbi_rest_*` - Not available for SSAS

## Example Workflow in VS Code

1. **Connect:**
   ```
   @workspace Use #mcp_ssas-internal_pbi_connect to connect to kmdbsprod63.bdk.kme.intern database "KM BI"
   ```

2. **Explore:**
   ```
   @workspace Use #mcp_ssas-internal_pbi_list_tables to show me the available cubes
   ```

3. **Get Details:**
   ```
   @workspace Use #mcp_ssas-internal_pbi_describe_table for the "Model" cube
   ```

4. **Query:**
   ```
   @workspace Use #mcp_ssas-internal_pbi_query_data to run this MDX: 
   SELECT {[Measures].[SUMFinance Actual Amount DKK]} ON COLUMNS FROM [Model]
   ```

## Troubleshooting

### Connection hangs or fails
- Verify network access: `ping kmdbsprod63.bdk.kme.intern`
- Check Windows permissions on SSAS server
- Ensure ADOMD.NET is installed (already configured in this repo)

### "Invalid MDX query" errors
- Remember: Use MDX syntax, not DAX
- Cube names in brackets: `[Model]`
- Check measure and dimension names with `pbi_describe_table`

### Tools not appearing
- Restart VS Code to reload MCP servers
- Check Output panel for MCP server errors

## Available Databases

Based on discovery, you have access to:

### KM BI Database
- **Model** cube (161 dimensions)
- **Finance** cube
- **Sales** cube
- **Service** cube
- **KM Training** cube
- **CRM** cube

### Super BI Database
- (List cubes by connecting to this database)

To switch databases, reconnect with a different `initial_catalog` value.

## Quick Reference

| Task | Tool | Parameters |
|------|------|------------|
| Connect | `pbi_connect` | `xmla_endpoint`, `initial_catalog` |
| List cubes | `pbi_list_tables` | none |
| Cube details | `pbi_describe_table` | `table_name` |
| Run query | `pbi_query_data` | `query`, `max_rows` |

## Next Steps

Now that Windows authentication is working:
1. Try connecting to the server
2. Explore the available cubes
3. Start querying your data with MDX

Happy querying! 🎉
