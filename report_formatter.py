from rqa_validator.models.api_models import PipelineResponse

def format_comment_adf(response: PipelineResponse) -> dict:
    """
    Formats the PipelineResponse into a high-level Atlassian Document Format (ADF) comment.
    Because detailed errors are placed in an attached Excel file, this only provides a summary.
    """
    is_success = response.success
    status_icon = "✅" if is_success else "❌"
    status_text = "VALIDATION PASSED" if is_success else "VALIDATION FAILED"
    
    summary = response.summary
    
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
                    {"type": "text", "text": "Dataset Type: "},
                    {"type": "text", "text": response.metadata.dataset_type, "marks": [{"type": "strong"}]}
                ]
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Errors: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": f"{summary.errors + summary.admin_errors} | "},
                    {"type": "text", "text": "Warnings: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": f"{summary.warnings} | "},
                    {"type": "text", "text": "Info: ", "marks": [{"type": "strong"}]},
                    {"type": "text", "text": f"{summary.info}"}
                ]
            }
        ]
    }
    
    if not is_success:
        adf_document["content"].append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Please download the attached Excel report for granular details and exact row numbers.", "marks": [{"type": "em"}]}
            ]
        })
    else:
        adf_document["content"].append({
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "The dataset meets all validation requirements and is ready for the warehouse."}
            ]
        })

    return adf_document
