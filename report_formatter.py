from typing import Optional
from importlib.metadata import version, PackageNotFoundError
from rqa_validator.models.api_models import PipelineResponse

try:
    JIVE_VERSION = version("jive-jira-integration")
except PackageNotFoundError:
    JIVE_VERSION = "0.1.0"

def format_comment_adf(
    issue_key: str,
    response: PipelineResponse, 
    attachment_url: Optional[str] = None,
    repo_url: Optional[str] = None,
    repo_action: Optional[str] = None,
    original_dataset_type: Optional[str] = None
) -> dict:
    """
    Formats the PipelineResponse into a premium Atlassian Document Format (ADF) comment
    specially optimized for Jira Service Management (JSM) portals.
    """
    is_success = response.success
    panel_type = "success" if is_success else "error"
    status_text = "✅ JIVE VALIDATION PASSED" if is_success else "❌ JIVE VALIDATION FAILED"
    
    # Base structure for ADF
    adf_document = {
        "version": 1,
        "type": "doc",
        "content": []
    }
    
    # 1. Gorgeous Native ADF Color Panel for Status
    adf_document["content"].append({
        "type": "panel",
        "attrs": {
            "panelType": panel_type
        },
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": status_text, "marks": [{"type": "strong"}]}
                ]
            }
        ]
    })
    
    # 2. Portal Context Info Card (Nested in a Note Panel)
    context_list = []
    
    # Target Action Bullet
    context_list.append({
        "type": "listItem",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Target Request Action: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": str(repo_action) if repo_action else "Archive/Publish (Standard)"}
                ]
            }
        ]
    })
    
    # IMPACT Repository URL Bullet
    repo_node_content = [{"type": "text", "text": "IMPACT Repository Resource: ", "marks": [{"type": "strong"}]}]
    if repo_url:
        repo_node_content.append({
            "type": "text",
            "text": "Link to Submitted Resource 🌐",
            "marks": [
                {"type": "strong"},
                {
                    "type": "link",
                    "attrs": {"href": repo_url}
                }
            ]
        })
    else:
        repo_node_content.append({"type": "text", "text": "Not Provided (No link specified)"})
        
    context_list.append({
        "type": "listItem",
        "content": [
            {
                "type": "paragraph",
                "content": repo_node_content
            }
        ]
    })
    
    # Dataset Format Bullet
    dataset_display = original_dataset_type.upper() if original_dataset_type else "Unknown"
    fallback_type = getattr(response.metadata, 'dataset_type', 'Unknown') if hasattr(response, 'metadata') and response.metadata else "Unknown"
    context_list.append({
        "type": "listItem",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Dataset Format: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": f"{dataset_display} "},
                    {"type": "text", "text": f"(pipeline runner: {fallback_type})", "marks": [{"type": "em"}]}
                ]
            }
        ]
    })
    
    adf_document["content"].append({
        "type": "panel",
        "attrs": {
            "panelType": "note"
        },
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "JSM Form Submission Context:", "marks": [{"type": "strong"}]}
                ]
            },
            {
                "type": "bulletList",
                "content": context_list
            }
        ]
    })
    
    # 3. Validation Summary Table (for actionable issues)
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
 
    if actionable_issues:
        table_rows = [
            {
                "type": "tableRow",
                "content": [
                    {
                        "type": "tableHeader",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Validation Check Name", "marks": [{"type": "strong"}]}]}]
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
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Summary of Validation Issues:", "marks": [{"type": "strong"}]}
            ]
        })
        
        adf_document["content"].append({
            "type": "table",
            "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
            "content": table_rows
        })
 
    # 4. Clear Actionable Portal Next-Steps
    passed_items = getattr(response, 'passed', None) or []
    passed_rules = set()
    for item in passed_items:
        rule = item.get('rule') if isinstance(item, dict) else getattr(item, 'rule', 'Unknown')
        passed_rules.add(rule)
        
    num_passed = len(passed_rules)
    passed_list_str = ", ".join(sorted(passed_rules))
    passed_msg = f"{num_passed} core quality checks passed successfully ✅ ({passed_list_str})." if num_passed > 0 else "No core checks passed."
    
    adf_document["content"].append({
        "type": "paragraph",
        "content": [
            {"type": "text", "text": passed_msg, "marks": [{"type": "em"}]}
        ]
    })
    
    if not is_success:
        adf_document["content"].append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "🚨 Action Required:", "marks": [{"type": "strong"}]}
            ]
        })
        adf_document["content"].append({
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Download the newly generated report spreadsheet "},
                                {"type": "text", "text": f"JIVE_Validation_Report_{issue_key}.xlsx", "marks": [{"type": "strong"}]},
                                {"type": "text", "text": " directly from this ticket's "},
                                {"type": "text", "text": "Attachments files list", "marks": [{"type": "strong"}]},
                                {"type": "text", "text": "."}
                            ]
                        }
                    ]
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Open the report sheet to review row-by-row cell errors (highlighted in red) to identify validation failures."}
                            ]
                        }
                    ]
                },
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "Correct the highlighted inconsistencies in your source dataset, then "},
                                {"type": "text", "text": "re-upload the updated Excel sheet", "marks": [{"type": "strong"}]},
                                {"type": "text", "text": " to trigger automated re-validation."}
                            ]
                        }
                    ]
                }
            ]
        })
    else:
        adf_document["content"].append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "🎉 Next Steps:", "marks": [{"type": "strong"}]}
            ]
        })
        adf_document["content"].append({
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "No further action is required. The global data engineering pipelines will automatically sync this verified resource and proceed with routing shortly."}
                            ]
                        }
                    ]
                }
            ]
        })
        
    # 5. Micro-Performance Stat Footer
    adf_document["content"].append({"type": "rule"})
    
    timestamp_str = response.metadata.timestamp if hasattr(response, 'metadata') and response.metadata and hasattr(response.metadata, 'timestamp') else "N/A"
    adf_document["content"].append({
        "type": "paragraph",
        "content": [
            {"type": "text", "text": f"JIVE Automated Validation Engine v{JIVE_VERSION} | ", "marks": [{"type": "em"}]},
            {"type": "text", "text": "Validated at: ", "marks": [{"type": "em"}, {"type": "strong"}]},
            {"type": "text", "text": timestamp_str, "marks": [{"type": "em"}]}
        ]
    })
    
    return adf_document
