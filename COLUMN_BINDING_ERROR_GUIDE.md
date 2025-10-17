# Power BI Column Source Binding Error - Troubleshooting Guide

## Error Description
```
Column '<oii>Product Hierarchy Number</oii>' in table '<oii>Product Hierarchy</oii>' does not have its source pipeline rowset column specified. Either provide out-of-line bindings for the column or set the 'SourceColumn' property.
```

## What This Error Means

This error occurs when Power BI cannot determine which source column should map to a specific column in your data model. The `<oii>` tags indicate "out-of-line identifier" which suggests that the column mapping has become disconnected from its source.

## Common Causes

1. **Source Column Renamed/Removed**: The source column in your data source was renamed or deleted
2. **Data Source Connection Changed**: The underlying data source structure changed
3. **Import/Export Issues**: Model was imported/exported and column mappings were lost
4. **Query Changes**: Power Query transformations changed the column names or structure
5. **Incremental Refresh Issues**: Problems with incremental refresh partition management

## Solutions to Try

### 1. Check Power Query Editor
1. Open **Power BI Desktop**
2. Go to **Transform Data** (Power Query Editor)
3. Navigate to the **Product Hierarchy** table
4. Look for the **Product Hierarchy Number** column
5. Check if there are any errors or warnings in the Applied Steps

### 2. Refresh Data Source Schema
1. In Power Query Editor, right-click on your data source
2. Select **Refresh Preview** or **Refresh**
3. Check if the source column still exists
4. If renamed, update the column reference

### 3. Fix Column Mapping Manually
1. In Power Query Editor, find the step where the column is created/renamed
2. Update the step to reference the correct source column
3. If using a custom column, ensure the formula is correct

### 4. Re-create the Column Reference
If the column mapping is completely broken:
1. Delete the current **Product Hierarchy Number** column
2. Re-add it from the source with the correct name
3. Ensure any dependencies (relationships, measures) are updated

### 5. Check Data Source Structure
Verify in your source system that:
- The column still exists
- The column name hasn't changed
- Data types are compatible
- You have permissions to access the column

### 6. Advanced: Edit Model Metadata (Power BI Desktop)
1. Save your .pbix file
2. Open with a text editor or use Tabular Editor
3. Look for the `Product Hierarchy Number` column definition
4. Ensure the `SourceColumn` property is correctly set
5. **⚠️ Warning: Only do this if you're comfortable with advanced editing**

## Prevention Tips

1. **Use Stable Column Names**: Avoid changing source column names frequently
2. **Document Dependencies**: Keep track of which model columns depend on which source columns
3. **Version Control**: Use source control for your Power BI files
4. **Test Changes**: Always test schema changes in development before production
5. **Use Parameters**: Use Power Query parameters for dynamic data source connections

## Power Query M Code Example

If you need to recreate the column mapping in Power Query:

```m
let
    Source = YourDataSource,
    // Rename column if source name changed
    RenamedColumn = Table.RenameColumns(Source, {{"OldColumnName", "Product Hierarchy Number"}}),
    
    // Or add custom column if calculation needed
    AddedCustomColumn = Table.AddColumn(RenamedColumn, "Product Hierarchy Number", 
        each [SourceColumnName], 
        type text)
in
    AddedCustomColumn
```

## DAX Considerations

If this column is used in DAX measures or calculated columns, you may need to:

1. Update any DAX references to use the correct column name
2. Check that relationships using this column are still valid
3. Refresh any calculated tables that depend on this column

## When to Contact Support

Contact your Power BI administrator or Microsoft Support if:
- The error persists after trying all solutions
- You're using Power BI Service and can't access Power Query Editor
- The issue affects multiple tables or datasets
- You suspect a platform-level issue

## Additional Resources

- [Power BI Troubleshooting Documentation](https://docs.microsoft.com/en-us/power-bi/troubleshoot/)
- [Power Query Editor Documentation](https://docs.microsoft.com/en-us/power-query/)
- [Tabular Editor for Advanced Model Editing](https://tabulareditor.github.io/)