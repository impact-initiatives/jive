import os
from pathlib import Path

from models import JiraSubmissionPayload
from jira_client import JiraClient
from report_formatter import format_comment_adf
from logger import get_logger
from rqa_validator.orchestrator.validation_pipeline import ValidationPipeline
from rqa_validator.models.api_models import PipelineResponse

logger = get_logger("jive.worker_utils")
MAX_JIRA_ATTACHMENT_MB = int(os.getenv("JIVE_MAX_ATTACHMENT_MB", "250"))

def check_idempotency(payload: JiraSubmissionPayload, attachments: list) -> bool:
    """Returns True if the validation should be skipped due to an up-to-date report."""
    # Idempotency guard: skip if a JIVE report already exists and is newer than the newest dataset
    expected_report_name = f"JIVE_Validation_Report_{payload.issue_key}.xlsx"
    
    report_attachment = next((a for a in attachments if a.get("filename") == expected_report_name), None)
    
    # Find all non-report Excel dataset attachments
    dataset_attachments = [
        a for a in attachments
        if a.get("filename", "").endswith(".xlsx") and a.get("filename") != expected_report_name
    ]
    # Sort dataset attachments with newest first
    dataset_attachments.sort(key=lambda a: a.get("created", ""), reverse=True)
    latest_dataset = dataset_attachments[0] if dataset_attachments else None
    
    skip_validation = False
    if report_attachment:
        if latest_dataset:
            skip_validation = report_attachment.get("created", "") > latest_dataset.get("created", "")
        else:
            # If there's no dataset attachment, the dataset is externally hosted (ProForma link, secure_link).
            # We must skip validation to prevent infinite loops when the JIVE report attachment itself 
            # triggers an issue_updated webhook.
            skip_validation = True
            
    if payload.force_revalidation:
        logger.info("Idempotency guard bypassed via webhook payload flag", extra={"issue_key": payload.issue_key})
        return False
        
    force_validation = os.getenv("JIVE_FORCE_VALIDATION", "False").lower() in ("true", "1")
    if not force_validation and skip_validation:
        logger.warning(
            "Idempotency: JIVE report is up to date — skipping re-validation",
            extra={"issue_key": payload.issue_key, "report": expected_report_name},
        )
        return True
    return False

def download_dataset(jira: JiraClient, payload: JiraSubmissionPayload, tmp_path: Path, resolved_issue_id: str, attachments: list, proforma_answers: dict = None) -> Path | None:
    """Downloads the dataset attachment or resolves external links. Returns Path if successful, None otherwise."""
    logger.info("Resolving dataset file", extra={"issue_key": payload.issue_key})
    dataset_path = jira.resolve_dataset(
        payload.issue_key,
        tmp_path,
        issue_id=resolved_issue_id,
        attachments=attachments,
        secure_link=payload.secure_link,
        proforma_answers=proforma_answers,
    )

    if not dataset_path:
        error_adf = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": "Failed to download dataset. No valid Excel attachment or repository link found.",
                        }
                    ],
                }
            ],
        }
        jira.post_comment(payload.issue_key, error_adf)
        logger.warning("No Excel dataset resolved", extra={"issue_key": payload.issue_key})
        return None
        
    return dataset_path

def resolve_context(jira: JiraClient, payload: JiraSubmissionPayload, resolved_issue_id: str, proforma_answers: dict = None) -> tuple[str, str | None, str | None]:
    """Parses ProForma answers to extract context variables (dataset type, repo URL, repo action)."""
    dataset_type = payload.dataset_type
    repo_url = None
    repo_action = None
    
    if proforma_answers:
        # Dynamically detect dataset type and other context fields from ProForma answers if available
        # Extract dataset type
        needle = jira.proforma_dataset_type_label.lower()
        for label, val in proforma_answers.items():
            if needle in label.lower():
                val_clean = val.strip().lower()
                if "jmmi" in val_clean:
                    dataset_type = "jmmi"
                elif "msna" in val_clean:
                    dataset_type = "msna"
                elif "esnfi" in val_clean:
                    dataset_type = "esnfi"
                else:
                    dataset_type = val_clean
                logger.info("Detected dataset type dynamically from ProForma answers", 
                            extra={"issue_key": payload.issue_key, "dataset_type": dataset_type})
        
        # Extract repository resource URL and action type
        for label, val in proforma_answers.items():
            if "link to the resource" in label.lower() or "repository" in label.lower():
                if val and val.strip().startswith("http"):
                    repo_url = val.strip()
            if "published or archived" in label.lower():
                repo_action = val.strip()
                
    return dataset_type, repo_url, repo_action

def run_validation(dataset_path: Path, dataset_type: str, payload: JiraSubmissionPayload) -> PipelineResponse:
    """Executes the validation pipeline against the dataset and returns the structured response."""
    # Ensure we only pass supported types to the pipeline, otherwise fall back to generic "other"
    SUPPORTED_SCHEMA_TYPES = {"jmmi", "msna", "other"}
    pipeline_dataset_type = dataset_type
    if dataset_type not in SUPPORTED_SCHEMA_TYPES:
        logger.info(
            "Unrecognized dataset type - falling back to generic 'other' dynamic validation",
            extra={"issue_key": payload.issue_key, "original_type": dataset_type, "fallback_type": "other"}
        )
        pipeline_dataset_type = "other"

    logger.info("Running validation pipeline", extra={"issue_key": payload.issue_key, "dataset_type": dataset_type, "pipeline_type": pipeline_dataset_type})
    pipeline = ValidationPipeline(dataset_type=pipeline_dataset_type)
    response_dict = pipeline.run(dataset_path)
    return PipelineResponse(**response_dict)

def publish_results(jira: JiraClient, payload: JiraSubmissionPayload, response: PipelineResponse, excel_report_path: Path, repo_url: str | None, repo_action: str | None, dataset_type: str):
    """Handles uploading the report file to Jira and posting the summary ADF comment."""
    
    file_size_mb = excel_report_path.stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_JIRA_ATTACHMENT_MB:
        logger.warning(
            "Excel report too large for Jira attachment — skipping upload",
            extra={"issue_key": payload.issue_key, "size_mb": round(file_size_mb, 2), "limit_mb": MAX_JIRA_ATTACHMENT_MB},
        )
    else:
        logger.info("Attempting to upload public JSM attachment", extra={"issue_key": payload.issue_key, "size_mb": round(file_size_mb, 2)})
        jsm_success = False
        if payload.project_key:
            jsm_success = jira.upload_public_jsm_attachment(payload.issue_key, payload.project_key, excel_report_path)
        
        if not jsm_success:
            logger.info("JSM public upload failed or skipped (missing project_key). Falling back to standard Jira attachment.", extra={"issue_key": payload.issue_key})
            jira.upload_attachment(payload.issue_key, excel_report_path)

    # Format comment (the report will be attached directly to the ticket and visible on the portal)
    adf_summary = format_comment_adf(
        payload.issue_key,
        response,
        attachment_url=None,
        repo_url=repo_url,
        repo_action=repo_action,
        original_dataset_type=dataset_type
    )

    if file_size_mb > MAX_JIRA_ATTACHMENT_MB:
        adf_summary["content"].append({
            "type": "paragraph",
            "content": [{
                "type": "text",
                "text": f"⚠️ The validation report ({file_size_mb:.1f}MB) exceeds the Jira attachment limit ({MAX_JIRA_ATTACHMENT_MB}MB). Please contact the JIVE team to retrieve the full report.",
                "marks": [{"type": "strong"}],
            }],
        })

    logger.info("Posting summary comment", extra={"issue_key": payload.issue_key})
    jira.post_comment(payload.issue_key, adf_summary)
