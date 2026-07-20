from typing import Any

from .config import get_settings
from .models import PipelineResponse, ResultItemModel

settings = get_settings()

try:
    with open(settings.jive_version_file) as f:
        jive_version = f.read().strip()
except Exception:
    jive_version = "unknown"


def format_comment_adf(
    issue_key: str,
    response: PipelineResponse,
    attachment_url: str | None = None,
    repo_url: str | None = None,
    repo_action: str | None = None,
    original_dataset_type: str | None = None,
) -> dict[str, Any]:
    """
    Formats the PipelineResponse into a premium Atlassian Document Format (ADF) comment
    specially optimized for Jira Service Management (JSM) portals.
    """
    is_success = response.success
    panel_type = "success" if is_success else "error"
    status_text = "✅ JIVE VALIDATION PASSED" if is_success else "❌ JIVE VALIDATION FAILED"

    # Base structure for ADF
    adf_document: dict[str, Any] = {"version": 1, "type": "doc", "content": []}

    # 1. Gorgeous Native ADF Color Panel for Status
    adf_document["content"].append(
        {
            "type": "panel",
            "attrs": {"panelType": panel_type},
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": status_text, "marks": [{"type": "strong"}]}
                    ],
                }
            ],
        }
    )

    # 2. Portal Context Info Card (Nested in a Note Panel)
    context_list = []

    # Target Action Bullet
    context_list.append(
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Target Request Action: ",
                            "marks": [{"type": "strong"}],
                        },
                        {
                            "type": "text",
                            "text": str(repo_action)
                            if repo_action is not None
                            else "Archive/Publish (Standard)",
                        },
                    ],
                }
            ],
        }
    )

    # IMPACT Repository URL Bullet
    repo_node_content = [
        {"type": "text", "text": "IMPACT Repository Resource: ", "marks": [{"type": "strong"}]}
    ]
    if repo_url is not None:
        repo_node_content.append(
            {
                "type": "text",
                "text": "Link to Submitted Resource 🌐",
                "marks": [{"type": "strong"}, {"type": "link", "attrs": {"href": repo_url}}],
            }
        )
    else:
        repo_node_content.append({"type": "text", "text": "Not Provided (No link specified)"})

    context_list.append(
        {"type": "listItem", "content": [{"type": "paragraph", "content": repo_node_content}]}
    )

    # Dataset Format Bullet
    dataset_display = original_dataset_type.upper() if original_dataset_type else "Unknown"
    fallback_type = response.metadata.dataset_type
    context_list.append(
        {
            "type": "listItem",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "Dataset Format: ", "marks": [{"type": "strong"}]},
                        {"type": "text", "text": f"{dataset_display} "},
                        {
                            "type": "text",
                            "text": f"(pipeline runner: {fallback_type})",
                            "marks": [{"type": "em"}],
                        },
                    ],
                }
            ],
        }
    )

    adf_document["content"].append(
        {
            "type": "panel",
            "attrs": {"panelType": "note"},
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "JSM Form Submission Context:",
                            "marks": [{"type": "strong"}],
                        }
                    ],
                },
                {"type": "bulletList", "content": context_list},
            ],
        }
    )

    # 3. Validation Summary Table (for actionable issues)
    actionable_issues: list[tuple[str, str, str, int]] = []

    def extract_issues(items: list[ResultItemModel], severity: str, icon: str):
        if not items:
            return
        rule_counts: dict[str, int] = {}
        for item in items:
            rule_counts[item.rule] = rule_counts.get(item.rule, 0) + 1

        for rule, count in rule_counts.items():
            actionable_issues.append((rule, severity, icon, count))

    extract_issues(response.errors, "Error", "❌")
    extract_issues(response.admin_errors, "Error", "❌")
    extract_issues(response.warnings, "Warning", "⚠️")

    if actionable_issues:
        table_rows = [
            {
                "type": "tableRow",
                "content": [
                    {
                        "type": "tableHeader",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Validation Check Name",
                                        "marks": [{"type": "strong"}],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "type": "tableHeader",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Severity",
                                        "marks": [{"type": "strong"}],
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "type": "tableHeader",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Issues Found",
                                        "marks": [{"type": "strong"}],
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ]

        for rule, severity, icon, count in actionable_issues:
            table_rows.append(
                {
                    "type": "tableRow",
                    "content": [
                        {
                            "type": "tableCell",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": rule}],
                                }
                            ],
                        },
                        {
                            "type": "tableCell",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": f"{icon} {severity}"}],
                                }
                            ],
                        },
                        {
                            "type": "tableCell",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": str(count)}],
                                }
                            ],
                        },
                    ],
                }
            )

        adf_document["content"].append(
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Summary of Validation Issues:",
                        "marks": [{"type": "strong"}],
                    }
                ],
            }
        )

        adf_document["content"].append(
            {
                "type": "table",
                "attrs": {"isNumberColumnEnabled": False, "layout": "default"},
                "content": table_rows,
            }
        )

    # 4. Clear Actionable Portal Next-Steps

    # Collect all rules that had at least one error/warning
    actionable_rule_names = {rule for rule, _, _, _ in actionable_issues}

    passed_items = response.passed
    passed_rules: set[str] = set()
    for item in passed_items:
        rule = item.rule
        # Only consider a rule "passed" if it never triggered an error/warning
        if rule not in actionable_rule_names:
            passed_rules.add(rule)

    num_passed = len(passed_rules)
    passed_list_str = ", ".join(sorted([str(r) for r in passed_rules]))
    passed_msg = (
        f"{num_passed} core quality checks passed successfully ✅ ({passed_list_str})."
        if num_passed > 0
        else "No core checks passed."
    )

    adf_document["content"].append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": passed_msg, "marks": [{"type": "em"}]}],
        }
    )

    if not is_success:
        adf_document["content"].append(
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "🚨 Action Required:", "marks": [{"type": "strong"}]}
                ],
            }
        )
        adf_document["content"].append(
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Download the newly generated report spreadsheet ",
                                    },
                                    {
                                        "type": "text",
                                        "text": f"JIVE_Validation_Report_{issue_key}.xlsx",
                                        "marks": [{"type": "strong"}],
                                    },
                                    {"type": "text", "text": " directly from this ticket's "},
                                    {
                                        "type": "text",
                                        "text": "Attachments files list",
                                        "marks": [{"type": "strong"}],
                                    },
                                    {"type": "text", "text": "."},
                                ],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Open the report sheet to review row-by-row cell"
                                        + " errors (highlighted in red) to identify validation "
                                        + "failures.",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Correct the highlighted inconsistencies in your"
                                        + " source dataset, then ",
                                    },
                                    {
                                        "type": "text",
                                        "text": "re-upload the updated Excel sheet",
                                        "marks": [{"type": "strong"}],
                                    },
                                    {
                                        "type": "text",
                                        "text": " to trigger automated re-validation.",
                                    },
                                ],
                            }
                        ],
                    },
                ],
            }
        )
        adf_document["content"].append(
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Validation Resources:", "marks": [{"type": "strong"}]}
                ],
            }
        )
        for doc in settings.jive_documentation:
            for name, url in doc.items():
                adf_document["content"].append(
                    {
                        "type": "bulletList",
                        "content": [
                            {
                                "type": "listItem",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": f"{name}",
                                                "marks": [
                                                    {
                                                        "type": "link",
                                                        "attrs": {
                                                            "href": f"{url}",
                                                            "title": f"{name}",
                                                        },
                                                    }
                                                ],
                                            },
                                        ],
                                    }
                                ],
                            },
                        ],
                    }
                )
    else:
        adf_document["content"].append(
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "🎉 Next Steps:", "marks": [{"type": "strong"}]}
                ],
            }
        )
        adf_document["content"].append(
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "No further action is required. The global data"
                                        + " engineering pipelines will automatically sync this"
                                        + " verified resource and proceed with routing shortly.",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        )

    # 5. Micro-Performance Stat Footer
    adf_document["content"].append({"type": "rule"})

    adf_document["content"].append(
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": f"JIVE v{jive_version} | ",
                    "marks": [{"type": "em"}],
                },
                {
                    "type": "text",
                    "text": f"Argus v{response.metadata.version} | ",
                    "marks": [{"type": "em"}],
                },
                {
                    "type": "text",
                    "text": "Validated at: ",
                    "marks": [{"type": "em"}, {"type": "strong"}],
                },
                {
                    "type": "text",
                    "text": response.metadata.validation_date,
                    "marks": [{"type": "em"}],
                },
            ],
        }
    )

    return adf_document
