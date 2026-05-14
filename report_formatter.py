from rqa_validator.models.api_models import PipelineResponse

def format_comment_adf(response: PipelineResponse) -> dict:
    """
    Formats the PipelineResponse into a high-level Atlassian Document Format (ADF) comment.
    Because detailed errors are placed in an attached Excel file, this only provides a summary table.
    """
    is_success = response.success
    status_icon = "✅" if is_success else "❌"
    status_text = "VALIDATION PASSED" if is_success else "VALIDATION FAILED"
    
    dataset_type = getattr(response.metadata, 'dataset_type', 'Unknown') if hasattr(response, 'metadata') and response.metadata else "Unknown"
    
    # Base structure for ADF
    adf_document = {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 3},
                "content": [
                    {"type": "text", "text": f"{status_icon} {status_text}"}
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Dataset Type: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": dataset_type},
                    {"type": "text", "text": " | "},
                    {"type": "text", "text": "Validated at: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": response.metadata.timestamp if hasattr(response.metadata, 'timestamp') else "N/A"}
                ]
            }
        ]
    }
    
    # Collect actionable issues (Errors and Warnings)
    actionable_issues = []
    
    def extract_issues(items, severity, icon):
        if not items:
            return
        rule_counts = {}
        for item in items:
            rule = item.get('rule') if isinstance(item, dict) else getattr(item, 'rule', 'Unknown')
            rule_counts[rule] = rule_counts.get(rule, 0) + 1
            
        for rule, count in rule_counts.items():
            actionable_issues.append((rule, severity, icon, count))

    extract_issues(getattr(response, 'errors', []), "Error", "❌")
    extract_issues(getattr(response, 'admin_errors', []), "Error", "❌")
    extract_issues(getattr(response, 'warnings', []), "Warning", "⚠️")

    # Only add the table if there are actionable issues
    if actionable_issues:
        table_rows = [
            {
                "type": "tableRow",
                "content": [
                    {
                        "type": "tableHeader",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Check Name", "marks": [{"type": "strong"}]}]}]
                    },
                    {
                        "type": "tableHeader",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Severity", "marks": [{"type": "strong"}]}]}]
                    },
                    {
                        "type": "tableHeader",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Issues Found", "marks": [{"type": "strong"}]}]}]
                    }
                ]
            }
        ]
        
        for rule, severity, icon, count in actionable_issues:
            table_rows.append({
                "type": "tableRow",
                "content": [
                    {
                        "type": "tableCell",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(rule)}]}]
                    },
                    {
                        "type": "tableCell",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": f"{icon} {severity}"}]}]
                    },
                    {
                        "type": "tableCell",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": str(count)}]}]
                    }
                ]
            })
            
        adf_document["content"].append({
            "type": "table",
            "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
            "content": table_rows
        })

    # Build the footer note
    passed_items = getattr(response, 'passed', [])
    passed_rules = set()
    for item in passed_items:
        rule = item.get('rule') if isinstance(item, dict) else getattr(item, 'rule', 'Unknown')
        passed_rules.add(rule)
        
    num_passed = len(passed_rules)
    passed_list_str = ", ".join(sorted(passed_rules))
    
    if num_passed > 0:
        passed_msg = f"{num_passed} checks passed successfully ✅ ({passed_list_str})."
    else:
        passed_msg = "No checks passed successfully."

    if not is_success:
        adf_document["content"].append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": f"{passed_msg} Please download the attached Excel report for granular details.", "marks": [{"type": "em"}]}
            ]
        })
    else:
        adf_document["content"].append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": f"{passed_msg} The dataset meets all validation requirements and is ready for the warehouse."}
            ]
        })

    return adf_document
