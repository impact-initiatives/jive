from typing import Any

from argus.orchestrator.output_models import PipelineResponse
from argus.validators.base import ValidationResult, ValidatorResponse
from pydantic import Json

from .config import get_settings

settings = get_settings()


def format_comment_adf(
    issue_key: str,
    response: PipelineResponse,
    attachment_url: str | None = None,
    repo_url: str | None = None,
    repo_action: str | None = None,
    original_programme_type: str | None = None,
    original_output_type: str | None = None,
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
    repo_node_content: list[dict[str, Any]] = [
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
    dataset_display = (
        f"{original_programme_type.upper() if original_programme_type else 'Unknown'}"
        + f" {original_output_type.upper() if original_output_type else ''}"
    )
    fallback_type = response.metadata.programme_type + " " + response.metadata.output_type
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
    actionable_issues: list[tuple[str, str, str, tuple[int, int]]] = []

    def extract_issues(validators: list[ValidatorResponse], severity: str, icon: str):
        def validator_results(validator: ValidatorResponse) -> list[ValidationResult]:
            """A validator's results, tolerating None."""
            return validator.details or []

        if not validators:
            return
        for validator in validators:
            failed_checks = len(validator_results(validator))
            issues_found = sum(r.get_details_length() for r in validator_results(validator))
            actionable_issues.append(
                (validator.name, severity, icon, (failed_checks, issues_found))
            )

    extract_issues(response.errors, "Error", "❌")
    extract_issues(response.admin_errors, "Jive Error", "🔥")
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
                                        "text": "Failed Checks",
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
                                    "content": [{"type": "text", "text": str(count[0])}],
                                }
                            ],
                        },
                        {
                            "type": "tableCell",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": str(count[1])}],
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

    passed_rules = {
        validator.name
        for validator in response.passed
        if validator.name not in actionable_rule_names
    }

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
        documentation_list: Json[list[dict[str, str]]] = []
        if settings.jive_documentation is not None:
            jive_docs = settings.jive_documentation.get("jive")
            if jive_docs is not None:
                documentation_list.append(jive_docs)

            output_docs = settings.jive_documentation.get(response.metadata.output_type)
            if output_docs is not None:
                documentation_list.append(output_docs)

            programme_docs = settings.jive_documentation.get(response.metadata.programme_type)
            if programme_docs is not None:
                documentation_list.append(programme_docs)

        if documentation_list:
            adf_document["content"].append(
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Validation Resources:",
                            "marks": [{"type": "strong"}],
                        }
                    ],
                }
            )

            adf_jive_documentation: dict[str, Any] = {"type": "bulletList", "content": []}
            for doc in documentation_list:
                for name, url in doc.items():
                    _ = adf_jive_documentation["content"].append(
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
                    )
            adf_document["content"].append(adf_jive_documentation)
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
                                        "text": "No further action is required.",
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
                    "text": f"JIVE v{settings.jive_version} | ",
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
