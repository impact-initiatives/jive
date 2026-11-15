from pathlib import Path

from jira.jira_client import JiraClient
from jira.models import IssueAttachment
from jira.proforma_parser import ProformaParser
from jive_logging.logger import get_logger

from worker_base.models import JiraSubmissionPayload

from .impact_repo_client import ImpactRepoClient

logger = get_logger("jive.dataset_utils")


class DatasetResolutionError(Exception):
    """Raised when no dataset can be downloaded from any source."""

    pass


def resolve_dataset(
    jira: JiraClient,
    proforma: ProformaParser,
    impact_repo: ImpactRepoClient,
    issue_key: str,
    output_dir: Path,
    issue_id: str | None = None,
    attachments: list[IssueAttachment] | None = None,
    secure_link: str | None = None,
    proforma_answers: dict[str, str] | None = None,
) -> Path | None:
    """Orchestrates resolving the dataset using a fallback/priority strategy:

    1. Direct Attachment (Highest Priority): Check for any .xlsx/.xls files attached
    directly to the Jira ticket.
    2. IMPACT Repository (Secondary): Parse the ProForma form to extract the IMPACT
    Repository page URL and scrape/download.
    3. Webhook/Fallback Secure Link (Tertiary): Direct download from custom secure links.
    """
    logger.info("Starting dataset resolution workflow", extra={"issue_key": issue_key})

    # ── 1. Direct Attachment (Highest Priority) ──
    dataset_path = jira.download_proforma_attachment(issue_key, output_dir, attachments=attachments)
    if dataset_path:
        logger.info(
            "Successfully resolved dataset from Jira attachment",
            extra={"issue_key": issue_key, "resolved_filename": dataset_path.name},
        )
        return dataset_path

    # ── 2. IMPACT Repository via ProForma (Secondary) ──
    logger.info(
        "No direct attachment found, attempting ProForma form parsing",
        extra={"issue_key": issue_key},
    )

    if issue_id and proforma_answers:
        # Find label matching the repo label pattern (case-insensitive)
        page_url = None
        needle = proforma.settings.proforma_repository_label.lower()
        for label, val in proforma_answers.items():
            if needle in label.lower():
                page_url = val
                break

        if page_url:
            logger.info(
                "IMPACT Repository URL found in ProForma answers",
                extra={"issue_key": issue_key, "page_url": page_url},
            )
            excel_url = impact_repo.scrape_excel_url(page_url)
            if excel_url:
                filename = excel_url.rstrip("/").split("/")[-1] or f"{issue_key}.xlsx"
                output_path = output_dir / filename

                logger.info(
                    "Downloading scraped Excel file from Repository",
                    extra={"issue_key": issue_key, "url": excel_url},
                )
                success = impact_repo.download_excel(excel_url, output_path)
                if success:
                    logger.info(
                        "Successfully resolved dataset from IMPACT Repository scraping",
                        extra={
                            "issue_key": issue_key,
                            "resolved_filename": filename,
                        },
                    )
                    return output_path
            else:
                logger.warning(
                    "Failed to scrape Excel download link from repository page",
                    extra={"issue_key": issue_key, "page_url": page_url},
                )
        else:
            logger.info(
                "No IMPACT Repository URL found in ProForma answers",
                extra={"issue_key": issue_key},
            )
    else:
        logger.warning(
            "Could not resolve issue ID — skipping ProForma parsing",
            extra={"issue_key": issue_key},
        )

    # ── 3. Webhook/Fallback Secure Link (Tertiary) ──
    if secure_link:
        logger.info(
            "Attempting fallback secure link resolution",
            extra={"issue_key": issue_key, "secure_link": secure_link},
        )
        dataset_path = jira.download_from_secure_link(secure_link, output_dir)
        if dataset_path:
            logger.info(
                "Successfully resolved dataset from fallback secure link",
                extra={
                    "issue_key": issue_key,
                    "resolved_filename": dataset_path.name,
                },
            )
            return dataset_path

    return None


def download_dataset(
    jira: JiraClient,
    proforma: ProformaParser,
    payload: JiraSubmissionPayload,
    tmp_path: Path,
    resolved_issue_id: str,
    attachments: list[IssueAttachment] | None,
    proforma_answers: dict[str, str] | None = None,
) -> Path | None:
    """Downloads the dataset attachment or resolves external links.
    Returns Path if successful, None otherwise."""
    logger.info("Resolving dataset file", extra={"issue_key": payload.issue_key})
    impact_repo = ImpactRepoClient()
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
                            "text": "Failed to download dataset. No valid Excel attachment or"
                            + " repository link found.",
                        }
                    ],
                }
            ],
        }
        _ = jira.post_comment(payload.issue_key, error_adf)
        logger.warning("No Excel dataset resolved", extra={"issue_key": payload.issue_key})
        raise DatasetResolutionError(f"No dataset resolved for {payload.issue_key}")

    return dataset_path
