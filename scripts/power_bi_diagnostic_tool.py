#!/usr/bin/env python3
"""
Simple diagnostic script to help identify common Power BI model issues.
This script provides general guidance when direct connection isn't possible.
"""

import json
from datetime import datetime


def analyze_column_binding_error(error_message: str) -> dict:
    """Analyze a column binding error message and provide diagnostic information."""
    
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "error_type": "Column Source Binding Error",
        "severity": "High",
        "impact": "Model refresh will fail",
        "extracted_info": {},
        "recommendations": []
    }
    
    # Extract information from error message
    if "does not have its source pipeline rowset column specified" in error_message:
        analysis["extracted_info"]["root_cause"] = "Missing source column mapping"
        analysis["extracted_info"]["error_pattern"] = "Source Pipeline Rowset"
        
        # Extract column and table names if possible
        if "Column '" in error_message and "' in table '" in error_message:
            try:
                # Extract column name (handling <oii> tags)
                col_start = error_message.find("Column '") + 8
                col_end = error_message.find("' in table '")
                column_name = error_message[col_start:col_end]
                
                # Clean up <oii> tags
                column_name = column_name.replace("<oii>", "").replace("</oii>", "")
                
                # Extract table name
                table_start = error_message.find("' in table '") + 12
                table_end = error_message.find("'", table_start)
                table_name = error_message[table_start:table_end]
                
                # Clean up <oii> tags
                table_name = table_name.replace("<oii>", "").replace("</oii>", "")
                
                analysis["extracted_info"]["problematic_column"] = column_name
                analysis["extracted_info"]["problematic_table"] = table_name
                
            except Exception as e:
                analysis["extracted_info"]["extraction_error"] = str(e)
    
    # Add recommendations based on the error pattern
    analysis["recommendations"] = [
        {
            "priority": "High",
            "action": "Check Power Query Editor",
            "description": "Open Transform Data and verify the column exists in the source",
            "steps": [
                "Open Power BI Desktop",
                "Go to Transform Data",
                f"Navigate to '{analysis['extracted_info'].get('problematic_table', 'the affected table')}'",
                f"Look for '{analysis['extracted_info'].get('problematic_column', 'the problematic column')}'",
                "Check for errors in Applied Steps"
            ]
        },
        {
            "priority": "High", 
            "action": "Verify Source Data",
            "description": "Confirm the source column still exists and is accessible",
            "steps": [
                "Check if source column was renamed or deleted",
                "Verify data source connection is working",
                "Ensure you have permissions to access the column",
                "Check if data types are compatible"
            ]
        },
        {
            "priority": "Medium",
            "action": "Refresh Schema",
            "description": "Update the data source schema in Power Query",
            "steps": [
                "Right-click on data source in Power Query",
                "Select 'Refresh Preview'",
                "Check for schema changes",
                "Update column references if needed"
            ]
        },
        {
            "priority": "Medium",
            "action": "Fix Column Mapping",
            "description": "Manually correct the column source mapping",
            "steps": [
                "Find the step where column is created/referenced",
                "Update the step to use correct source column",
                "Test the query to ensure it works",
                "Apply changes and close Power Query Editor"
            ]
        },
        {
            "priority": "Low",
            "action": "Advanced Metadata Editing",
            "description": "Use advanced tools like Tabular Editor (expert users only)",
            "warning": "Only attempt if comfortable with model metadata editing",
            "steps": [
                "Backup your .pbix file first",
                "Use Tabular Editor to examine column definitions",
                "Verify SourceColumn property is correctly set",
                "Save and test the changes"
            ]
        }
    ]
    
    return analysis


def generate_diagnostic_report(error_message: str, output_file: str = None):
    """Generate a comprehensive diagnostic report for the error."""
    
    analysis = analyze_column_binding_error(error_message)
    
    # Create human-readable report
    report = f"""
# Power BI Model Diagnostic Report

## Error Analysis
- **Error Type**: {analysis['error_type']}
- **Severity**: {analysis['severity']}
- **Impact**: {analysis['impact']}
- **Analysis Time**: {analysis['timestamp']}

## Extracted Information
"""
    
    for key, value in analysis['extracted_info'].items():
        report += f"- **{key.replace('_', ' ').title()}**: {value}\n"
    
    report += "\n## Recommended Actions\n\n"
    
    for i, rec in enumerate(analysis['recommendations'], 1):
        report += f"### {i}. {rec['action']} (Priority: {rec['priority']})\n\n"
        report += f"{rec['description']}\n\n"
        
        if rec.get('warning'):
            report += f"⚠️ **Warning**: {rec['warning']}\n\n"
        
        report += "**Steps:**\n"
        for step in rec['steps']:
            report += f"- {step}\n"
        report += "\n"
    
    report += """
## Additional Resources

- **Power BI Documentation**: https://docs.microsoft.com/en-us/power-bi/
- **Power Query Documentation**: https://docs.microsoft.com/en-us/power-query/
- **Community Support**: https://community.powerbi.com/
- **Tabular Editor**: https://tabulareditor.github.io/

## Next Steps

1. Start with High priority recommendations
2. Test each solution in a development environment first
3. Document any schema changes for future reference
4. Consider implementing change management processes for data sources

---
*This report was generated automatically. For complex issues, consider consulting with a Power BI expert.*
"""
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ Diagnostic report saved to: {output_file}")
    
    return report


def main():
    """Main function to demonstrate the diagnostic tool."""
    
    # Example error message from the user
    error_message = """Column '<oii>Product Hierarchy Number</oii>' in table '<oii>Product Hierarchy</oii>' does not have its source pipeline rowset column specified. Either provide out-of-line bindings for the column or set the 'SourceColumn' property."""
    
    print("🔍 Power BI Model Diagnostic Tool")
    print("=" * 50)
    print(f"Analyzing error: {error_message[:100]}...")
    print()
    
    # Generate analysis
    analysis = analyze_column_binding_error(error_message)
    
    # Print summary
    print("📊 Analysis Summary:")
    print(f"   Error Type: {analysis['error_type']}")
    print(f"   Severity: {analysis['severity']}")
    print(f"   Table: {analysis['extracted_info'].get('problematic_table', 'Unknown')}")
    print(f"   Column: {analysis['extracted_info'].get('problematic_column', 'Unknown')}")
    print()
    
    print("🎯 Top Recommendations:")
    for i, rec in enumerate(analysis['recommendations'][:3], 1):
        print(f"   {i}. {rec['action']} ({rec['priority']} priority)")
    print()
    
    # Generate full report
    report_file = f"power_bi_diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report = generate_diagnostic_report(error_message, report_file)
    
    print("📋 Full diagnostic report generated!")
    print(f"   File: {report_file}")


if __name__ == "__main__":
    main()