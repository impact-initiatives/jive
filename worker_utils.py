import os
from datetime import datetime
from pathlib import Path

from models import JiraSubmissionPayload
from jira_client import JiraClient
from proforma_parser import ProformaParser
from impact_repo_client import ImpactRepoClient
from report_formatter import format_comment_adf
from logger import get_logger
from rqa_validator.orchestrator.validation_pipeline import ValidationPipeline
from rqa_validator.models.api_models import PipelineResponse

logger = get_logger("jive.worker_utils")
MAX_JIRA_ATTACHMENT_MB = int(os.getenv("JIVE_MAX_ATTACHMENT_MB", "250"))
SUPPORTED_SCHEMA_TYPES = {"jmmi", "msna", "other"}


class DatasetResolutionError(Exception):
    """Raised when no dataset can be downloaded from any source."""
    pass

def _parse_timestamp(ts_str: str) -> datetime:
    """Parse a Jira ISO 8601 timestamp string to a timezone-aware datetime.
    
    Falls back to datetime.min (UTC) if parsing fails, so that items with
    unparseable timestamps sort to the bottom.
    """
    if not ts_str:
        return datetime.min
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return datetime.min


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
    dataset_attachments.sort(key=lambda a: _parse_timestamp(a.get("created", "")), reverse=True)
    latest_dataset = dataset_attachments[0] if dataset_attachments else None
    
    skip_validation = False
    if report_attachment:
        if latest_dataset:
            report_ts = _parse_timestamp(report_attachment.get("created", ""))
            dataset_ts = _parse_timestamp(latest_dataset.get("created", ""))
            skip_validation = report_ts > dataset_ts
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

def resolve_dataset(
    jira: JiraClient,
    proforma: ProformaParser,
    impact_repo: ImpactRepoClient,
    issue_key: str,
    output_dir: Path,
    issue_id: str | None = None,
    attachments: list | None = None,
    secure_link: str | None = None,
    proforma_answers: dict | None = None
) -> Path | None:
    """Orchestrates resolving the dataset using a fallback/priority strategy:
    
    1. Direct Attachment (Highest Priority): Check for any .xlsx/.xls files attached directly to the Jira ticket.
    2. IMPACT Repository (Secondary): Parse the ProForma form to extract the IMPACT Repository page URL and scrape/download.
    3. Webhook/Fallback Secure Link (Tertiary): Direct download from custom secure links.
    """
    logger.info("Starting dataset resolution workflow", extra={"issue_key": issue_key})
    
    # ── 1. Direct Attachment (Highest Priority) ──
    dataset_path = jira.download_proforma_attachment(issue_key, output_dir, attachments=attachments)
    if dataset_path:
        logger.info("Successfully resolved dataset from Jira attachment", 
                    extra={"issue_key": issue_key, "resolved_filename": dataset_path.name})
        return dataset_path

    # ── 2. IMPACT Repository via ProForma (Secondary) ──
    logger.info("No direct attachment found, attempting ProForma form parsing", extra={"issue_key": issue_key})
    
    if issue_id and proforma_answers:
        
        # Find label matching the repo label pattern (case-insensitive)
        page_url = None
        needle = proforma.repo_label.lower()
        for label, val in proforma_answers.items():
            if needle in label.lower():
                page_url = val
                break
                
        if page_url:
            logger.info("IMPACT Repository URL found in ProForma answers", extra={"issue_key": issue_key, "page_url": page_url})
            excel_url = impact_repo.scrape_excel_url(page_url)
            if excel_url:
                filename = excel_url.rstrip("/").split("/")[-1] or f"{issue_key}.xlsx"
                output_path = output_dir / filename
                
                logger.info("Downloading scraped Excel file from Repository", extra={"issue_key": issue_key, "url": excel_url})
                success = impact_repo.download_excel(excel_url, output_path)
                if success:
                    logger.info("Successfully resolved dataset from IMPACT Repository scraping", 
                                extra={"issue_key": issue_key, "resolved_filename": filename})
                    return output_path
            else:
                logger.warning("Failed to scrape Excel download link from repository page", extra={"issue_key": issue_key, "page_url": page_url})
        else:
            logger.info("No IMPACT Repository URL found in ProForma answers", extra={"issue_key": issue_key})
    else:
        logger.warning("Could not resolve issue ID — skipping ProForma parsing", extra={"issue_key": issue_key})

    # ── 3. Webhook/Fallback Secure Link (Tertiary) ──
    if secure_link:
        logger.info("Attempting fallback secure link resolution", extra={"issue_key": issue_key, "secure_link": secure_link})
        dataset_path = jira.download_from_secure_link(secure_link, output_dir)
        if dataset_path:
            logger.info("Successfully resolved dataset from fallback secure link", 
                        extra={"issue_key": issue_key, "resolved_filename": dataset_path.name})
            return dataset_path

    return None

def download_dataset(
    jira: JiraClient,
    proforma: ProformaParser,
    impact_repo: ImpactRepoClient,
    payload: JiraSubmissionPayload,
    tmp_path: Path,
    resolved_issue_id: str,
    attachments: list,
    proforma_answers: dict | None = None
) -> Path | None:
    """Downloads the dataset attachment or resolves external links. Returns Path if successful, None otherwise."""
    logger.info("Resolving dataset file", extra={"issue_key": payload.issue_key})
    dataset_path = resolve_dataset(
        jira,
        proforma,
        impact_repo,
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
        raise DatasetResolutionError(f"No dataset resolved for {payload.issue_key}")
        
    return dataset_path

def resolve_context(proforma: ProformaParser, payload: JiraSubmissionPayload, resolved_issue_id: str, proforma_answers: dict | None = None) -> tuple[str, str | None, str | None]:
    """Parses ProForma answers to extract context variables (dataset type, repo URL, repo action)."""
    dataset_type = payload.dataset_type
    repo_url = None
    repo_action = None
    
    if proforma_answers:
        # Dynamically detect dataset type and other context fields from ProForma answers if available
        # Extract dataset type
        needle = proforma.dataset_type_label.lower()
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

    pipeline_dataset_type = dataset_type
    if dataset_type not in SUPPORTED_SCHEMA_TYPES:
        logger.info(
            "Unrecognized dataset type - falling back to generic 'other' dynamic validation",
            extra={"issue_key": payload.issue_key, "original_type": dataset_type, "fallback_type": "other"}
        )
        pipeline_dataset_type = "other"

    logger.info("Running validation pipeline", extra={"issue_key": payload.issue_key, "dataset_type": dataset_type, "pipeline_type": pipeline_dataset_type})
    pipeline = ValidationPipeline()
    response_dict = pipeline.run_all(dataset_path, pipeline_dataset_type)
    
    # rqa-validator's ValidationPipeline._compile_results outputs keys like 'error', 'warning', 'admin_error'
    # but PipelineResponse expects 'errors', 'warnings', 'admin_errors'.
    # We patch the response_dict before parsing it.
    key_mapping = {
        "error": "errors",
        "warning": "warnings",
        "admin_error": "admin_errors",
        "admin_info": "info"
    }
    
    patched_dict = {}
    for k, v in response_dict.items():
        if k in key_mapping:
            patched_dict[key_mapping[k]] = v
        else:
            patched_dict[k] = v
            
    # Also patch the summary dictionary keys
    if "summary" in patched_dict and isinstance(patched_dict["summary"], dict):
        patched_summary = {}
        for k, v in patched_dict["summary"].items():
            if k in key_mapping:
                patched_summary[key_mapping[k]] = v
            else:
                patched_summary[k] = v
        patched_dict["summary"] = patched_summary

    try:
        # 1. Attempt strict parsing (standard Pydantic validation)
        return PipelineResponse(**patched_dict)
    except Exception as e:
        logger.warning(
            "Failed strict Pydantic parsing of validation response. Attempting schema-tolerant model_construct fallback.",
            exc_info=e,
            extra={"issue_key": payload.issue_key}
        )
        try:
            # 2. Fallback 1: Construct the model directly, bypassing Pydantic input validation.
            # This handles extra fields, missing optional keys, or slight type discrepancies.
            return PipelineResponse.model_construct(
                success=patched_dict.get("success", False),
                summary=patched_dict.get("summary", {"passed": False, "admin_errors": 1, "errors": 0, "warnings": 0, "info": 0}),
                metadata=patched_dict.get("metadata", {"dataset_type": dataset_type}),
                errors=patched_dict.get("errors", []),
                admin_errors=patched_dict.get("admin_errors", []),
                warnings=patched_dict.get("warnings", []),
                info=patched_dict.get("info", []),
                passed=patched_dict.get("passed", [])
            )
        except Exception as fallback_err:
            logger.error(
                "Critical: Schema-tolerant model construction failed. Generating generic error report.",
                exc_info=fallback_err,
                extra={"issue_key": payload.issue_key}
            )
            # 3. Fallback 2: Generate a generic error response indicating formatting mismatch
            # so the worker pipeline completes gracefully without dead-lettering.
            return PipelineResponse.model_construct(
                success=False,
                summary={"passed": False, "admin_errors": 1, "errors": 0, "warnings": 0, "info": 0},
                metadata={"dataset_type": dataset_type},
                errors=[],
                warnings=[],
                info=[],
                admin_errors=[
                    {
                        "severity": "ADMIN",
                        "rule": "JIVE_SCHEMA_MISMATCH",
                        "message": (
                            "The validation pipeline executed successfully, but JIVE encountered "
                            "a schema format error when reading the results. Please contact support. "
                            f"Error details: {str(fallback_err)}"
                        )
                    }
                ]
            )

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
            upload_ok = jira.upload_attachment(payload.issue_key, excel_report_path)
            if not upload_ok:
                logger.error(
                    "Failed to upload validation report to Jira",
                    extra={"issue_key": payload.issue_key, "file": str(excel_report_path)},
                )

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
