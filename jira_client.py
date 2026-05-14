import os
import time
import requests
from pathlib import Path
from typing import Optional
from logger import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import logging

logger = get_logger("jive.jira_client")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

class JiraAPIError(Exception):
    """Raised when a Jira API call returns a retryable error."""
    pass


def _check_retryable(response: requests.Response):
    """Raises JiraAPIError if the response has a retryable status code."""
    if response.status_code in RETRYABLE_STATUS_CODES:
        raise JiraAPIError(
            f"Jira returned {response.status_code}: {response.text[:200]}"
        )


class JiraClient:
    def __init__(self):
        self.email = os.getenv("JIRA_API_EMAIL")
        self.token = os.getenv("JIRA_API_TOKEN")
        self.base_url = os.getenv("JIRA_BASE_URL", "https://reach-initiative.atlassian.net")

        if not self.email or not self.token:
            raise ValueError("JIRA_API_EMAIL and JIRA_API_TOKEN environment variables must be set")

        self.auth = (self.email, self.token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        self.secure_link_user = os.getenv("SECURE_LINK_USERNAME")
        self.secure_link_pass = os.getenv("SECURE_LINK_PASSWORD")
        self.secure_link_auth = (self.secure_link_user, self.secure_link_pass) if self.secure_link_user and self.secure_link_pass else None

        self.session = requests.Session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def post_comment(self, issue_key: str, adf_content: dict) -> bool:
        """Posts an Atlassian Document Format (ADF) comment to the issue."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        payload = {"body": adf_content}

        start = time.monotonic()
        response = self.session.post(url, json=payload, auth=self.auth, headers=self.headers, timeout=(5, 30))
        duration_ms = int((time.monotonic() - start) * 1000)

        _check_retryable(response)

        if response.status_code == 201:
            logger.info(
                "Comment posted",
                extra={"issue_key": issue_key, "status_code": 201, "duration_ms": duration_ms},
            )
            return True
        else:
            logger.error(
                "Failed to post comment",
                extra={"issue_key": issue_key, "status_code": response.status_code},
            )
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def upload_attachment(self, issue_key: str, file_path: Path) -> bool:
        """Uploads a file to the Jira issue as an attachment."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/attachments"

        headers = {
            "X-Atlassian-Token": "no-check",
            "Accept": "application/json",
        }

        with open(file_path, "rb") as f:
            files = {
                "file": (
                    file_path.name,
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            start = time.monotonic()
            response = self.session.post(url, headers=headers, auth=self.auth, files=files, timeout=(5, 120))
            duration_ms = int((time.monotonic() - start) * 1000)

        _check_retryable(response)

        if response.status_code == 200:
            logger.info(
                "Attachment uploaded",
                extra={
                    "issue_key": issue_key,
                    "status_code": 200,
                    "duration_ms": duration_ms,
                },
            )
            return True
        else:
            logger.error(
                "Failed to upload attachment",
                extra={"issue_key": issue_key, "status_code": response.status_code},
            )
            return False

    def get_attachments(self, issue_key: str) -> list:
        """Fetches the attachment list for a Jira ticket. Returns a list of attachment dicts.
        
        This is the single source of truth for attachment data — call this once
        and pass the result to both idempotency checks and download logic.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}?fields=attachment"
        try:
            response = self.session.get(url, auth=self.auth, headers=self.headers, timeout=(5, 30))
            _check_retryable(response)
            if response.status_code != 200:
                logger.error(
                    "Failed to fetch attachments",
                    extra={"issue_key": issue_key, "status_code": response.status_code},
                )
                return []
            return response.json().get("fields", {}).get("attachment", [])
        except Exception as e:
            logger.error("Error fetching attachments", exc_info=e, extra={"issue_key": issue_key})
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def download_proforma_attachment(self, issue_key: str, output_dir: Path, attachments: list | None = None) -> Optional[Path]:
        """Downloads the most recent Excel attachment from the Jira ticket.
        
        Args:
            issue_key: The Jira issue key.
            output_dir: Directory to save the downloaded file.
            attachments: Pre-fetched attachment list from get_attachments(). 
                         If None, fetches fresh (backward compatible).
        """
        if attachments is None:
            attachments = self.get_attachments(issue_key)

        xlsx_attachments = [
            a for a in attachments 
            if a.get("filename", "").endswith(".xlsx")
            and not a.get("filename", "").startswith("JIVE_Validation_Report_")
        ]
        
        if not xlsx_attachments:
            logger.warning("No Excel attachments found", extra={"issue_key": issue_key})
            return None

        #Sort by creation date descending (newest first) so we always grab the latest version
        #handle both new uploaded file or updated version
        xlsx_attachments.sort(key=lambda a: a.get("created", ""), reverse=True)
        latest_attachment = xlsx_attachments[0]

        filename = latest_attachment.get("filename", "")
        content_url = latest_attachment.get("content")
        
        logger.info(
            "Downloading most recent attachment",
            extra={"issue_key": issue_key, "url": content_url, "created": latest_attachment.get("created")}
        )

        output_path = output_dir / filename
        success = self._download_file_with_retry(content_url, output_path, auth=self.auth)
        if success:
            return output_path
        
        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _download_file_with_retry(self, url: str, output_path: Path, auth: Optional[tuple] = None) -> bool:
        """Helper method to download a file with retries."""
        start = time.monotonic()
        response = self.session.get(url, auth=auth, stream=True, timeout=(5, 300))
        duration_ms = int((time.monotonic() - start) * 1000)

        _check_retryable(response)

        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            logger.error(
                "Failed to download file content",
                extra={"url": url, "status_code": response.status_code, "duration_ms": duration_ms},
            )
            return False

    def download_from_secure_link(self, url: str, output_dir: Path, filename: str = "secure_dataset.xlsx") -> Optional[Path]:
        """Downloads the dataset from a provided secure link using optional Basic Auth."""
        logger.info(
            "Downloading from secure link",
            extra={"url": url},
        )
        
        output_path = output_dir / filename
        success = self._download_file_with_retry(url, output_path, auth=self.secure_link_auth)
        if success:
            return output_path
        return None

    def attachment_exists(self, issue_key: str, filename: str) -> bool:
        """Returns True if an attachment with the given filename already exists on the ticket.
        
           Prevent re-processing the same ticket twice.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}?fields=attachment"
        try:
            response = self.session.get(url, auth=self.auth, headers=self.headers, timeout=(5, 30))
            if response.status_code != 200:
                logger.warning(
                    "Could not fetch attachments for idempotency check",
                    extra={"issue_key": issue_key, "status_code": response.status_code},
                )
                return False
            attachments = response.json().get("fields", {}).get("attachment", [])
            return any(a.get("filename") == filename for a in attachments)
        except Exception as e:
            logger.warning(
                "Idempotency check failed — proceeding with validation",
                exc_info=e,
                extra={"issue_key": issue_key},
            )
            return False
