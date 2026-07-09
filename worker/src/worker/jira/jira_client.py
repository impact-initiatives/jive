import logging
import os
import time
import urllib.parse
from pathlib import Path

import requests
from requests.sessions import Session
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..logger import get_logger
from .models import (
    IssueAttachment,
    IssueAttachmentResponse,
    IssueResponse,
    ServiceDeskResponse,
    TemporaryAttachmentsResponse,
)

logger = get_logger("jive.jira_client")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _sanitize_url(url: str) -> str:
    """Remove query parameters from a URL to prevent token leakage in logs."""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))


class JiraAPIError(Exception):
    """Raised when a Jira API call returns a retryable error."""

    pass


def _check_retryable(response: requests.Response):
    """Raises JiraAPIError if the response has a retryable status code."""
    if response.status_code in RETRYABLE_STATUS_CODES:
        raise JiraAPIError(f"Jira returned {response.status_code}: {response.text[:200]}")


class JiraClient:
    def __init__(self):
        self.email: str | None = os.getenv("JIRA_API_EMAIL")
        self.token: str | None = os.getenv("JIRA_API_TOKEN")
        self.base_url: str = os.getenv("JIRA_BASE_URL", "NOT PROVIDED").rstrip("/")

        if not self.email or not self.token:
            raise ValueError("JIRA_API_EMAIL and JIRA_API_TOKEN environment variables must be set")

        self.auth: tuple[str, str] = (self.email, self.token)
        self.headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        self.secure_link_user: str | None = os.getenv("SECURE_LINK_USERNAME")
        self.secure_link_pass: str | None = os.getenv("SECURE_LINK_PASSWORD")
        self.secure_link_auth: tuple[str, str] | None = (
            (self.secure_link_user, self.secure_link_pass)
            if self.secure_link_user and self.secure_link_pass
            else None
        )

        self.session: Session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update(self.headers)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def post_comment(
        self,
        issue_key: str,
        adf_content: dict[
            str, int | str | list[dict[str, str | list[dict[str, str | list[dict[str, str]]]]]]
        ],
    ) -> bool:
        """Posts an Atlassian Document Format (ADF) comment to the issue."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
        payload = {"body": adf_content}

        start = time.monotonic()
        response = self.session.post(url, json=payload, timeout=(3.05, 30))
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
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def upload_attachment(self, issue_key: str, file_path: Path) -> bool:
        """Uploads a file to the Jira issue as an attachment."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/attachments"

        headers: dict[str, str | None] = {
            "X-Atlassian-Token": "no-check",
            "Accept": "application/json",
            "Content-Type": None,
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
            response = self.session.post(url, headers=headers, files=files, timeout=(3.05, 120))
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
            try:
                response_data = IssueAttachmentResponse.model_validate(response.json())
                if response_data.attachments:
                    content_url = response_data.attachments[0].content
                    logger.info(
                        "Attachment content URL",
                        extra={"issue_key": issue_key, "content_url": content_url},
                    )
            except Exception:
                pass
            return True
        else:
            logger.error(
                "Failed to upload attachment",
                extra={"issue_key": issue_key, "status_code": response.status_code},
            )
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_service_desk_id(self, project_key: str) -> str | None:
        """Fetch the Service Desk ID associated with a project key."""
        url = f"{self.base_url}/rest/servicedeskapi/servicedesk/{project_key}"
        response = self.session.get(url, timeout=(3.05, 30))
        _check_retryable(response)
        if response.status_code == 200:
            response_data = ServiceDeskResponse.model_validate(response.json())
            return response_data.id
        else:
            logger.warning(
                "Service Desk lookup returned non-200 status",
                extra={"project_key": project_key, "status_code": response.status_code},
            )
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def upload_public_jsm_attachment(
        self, issue_key: str, project_key: str, file_path: Path
    ) -> bool:
        """Uploads an attachment publicly to a Jira Service Management ticket so it is
        visible directly on the portal."""
        # 1. Fetch Service Desk ID
        service_desk_id = self.get_service_desk_id(project_key)
        if not service_desk_id:
            logger.error(
                "Failed to upload JSM attachment: could not resolve service desk ID for project",
                extra={"project_key": project_key},
            )
            return False

        # 2. Upload temporary file
        upload_url = (
            f"{self.base_url}/rest/servicedeskapi/servicedesk/{service_desk_id}/attachTemporaryFile"
        )
        headers = {
            "X-Atlassian-Token": "no-check",
            "Accept": "application/json",
            "Content-Type": None,
        }

        try:
            with open(file_path, "rb") as f:
                files = {
                    "file": (
                        file_path.name,
                        f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                }
                logger.info(
                    "Uploading temporary JSM attachment",
                    extra={"issue_key": issue_key, "service_desk_id": service_desk_id},
                )
                response = self.session.post(
                    upload_url, headers=headers, files=files, timeout=(3.05, 120)
                )
                _check_retryable(response)

                if response.status_code != 201:
                    logger.error(
                        "Failed to upload temporary JSM attachment",
                        extra={"issue_key": issue_key, "status_code": response.status_code},
                    )
                    return False

                response_data = TemporaryAttachmentsResponse.model_validate(response.json())
                if not response_data.temporaryAttachments:
                    logger.error(
                        "Temporary JSM attachment response contained no attachments",
                        extra={"issue_key": issue_key},
                    )
                    return False

                temp_attachment_id = response_data.temporaryAttachments[0].temporaryAttachmentId
                logger.info(
                    "Temporary JSM attachment uploaded successfully",
                    extra={"issue_key": issue_key, "temp_id": temp_attachment_id},
                )
        except Exception as e:
            logger.error(
                "Failed to upload temporary JSM attachment",
                exc_info=e,
                extra={"issue_key": issue_key},
            )
            return False

        # 3. Attach temporary file to request publicly
        attach_url = f"{self.base_url}/rest/servicedeskapi/request/{issue_key}/attachment"
        attach_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"temporaryAttachmentIds": [temp_attachment_id], "public": True}

        try:
            logger.info(
                "Confirming public JSM attachment on request", extra={"issue_key": issue_key}
            )
            response = self.session.post(
                attach_url, headers=attach_headers, json=payload, timeout=(3.05, 30)
            )
            _check_retryable(response)

            if response.status_code == 201:
                logger.info(
                    "Successfully attached file publicly to JSM portal request",
                    extra={"issue_key": issue_key},
                )
                return True
            else:
                logger.error(
                    "Failed to attach file publicly to JSM request",
                    extra={"issue_key": issue_key, "status_code": response.status_code},
                )
                return False
        except Exception as e:
            logger.error(
                "Failed to attach file publicly to JSM request",
                exc_info=e,
                extra={"issue_key": issue_key},
            )
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_attachments(self, issue_key: str) -> list[IssueAttachment] | None:
        """Fetches the attachment list for a Jira ticket. Returns a list of attachment dicts.

        This is the single source of truth for attachment data — call this once
        and pass the result to both idempotency checks and download logic.
        """
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}?fields=attachment"
        response = self.session.get(url, timeout=(3.05, 30))
        _check_retryable(response)
        if response.status_code != 200:
            logger.error(
                "Failed to fetch attachments",
                extra={"issue_key": issue_key, "status_code": response.status_code},
            )
            return None

        response_data = IssueResponse.model_validate(response.json())
        return response_data.fields.attachment

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_issue_id(self, issue_key: str) -> str | None:
        """Fetch the internal issue ID (integer string) using the issue key."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}?fields=id"
        logger.info(
            "Resolving issue ID from key", extra={"issue_key": issue_key, "url": _sanitize_url(url)}
        )
        response = self.session.get(url, timeout=(3.05, 30))
        _check_retryable(response)
        if response.status_code == 200:
            response_data = IssueResponse.model_validate(response.json())
            issue_id = response_data.id
            logger.info(
                "Resolved issue ID successfully",
                extra={"issue_key": issue_key, "issue_id": issue_id},
            )
            return issue_id
        else:
            logger.error(
                "Failed to resolve issue ID from key",
                extra={"issue_key": issue_key, "status_code": response.status_code},
            )
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def download_proforma_attachment(
        self, issue_key: str, output_dir: Path, attachments: list[IssueAttachment] | None = None
    ) -> Path | None:
        """Downloads the most recent Excel attachment from the Jira ticket.

        Args:
            issue_key: The Jira issue key.
            output_dir: Directory to save the downloaded file.
            attachments: Pre-fetched attachment list from get_attachments().
                         If None, fetches fresh (backward compatible).
        """
        if attachments is None:
            attachments = self.get_attachments(issue_key)

        if attachments is not None:
            xlsx_attachments = [
                a
                for a in attachments
                if a.filename.endswith(".xlsx")
                and not a.filename.startswith("JIVE_Validation_Report_")
            ]

            if not xlsx_attachments:
                logger.warning("No Excel attachments found", extra={"issue_key": issue_key})
                return None
        else:
            logger.warning("No attachments found", extra={"issue_key": issue_key})
            return None

        # Sort by creation date descending (newest first) so we always grab the latest version
        # handle both new uploaded file or updated version
        xlsx_attachments.sort(key=lambda a: a.created, reverse=True)
        latest_attachment = xlsx_attachments[0]

        filename = latest_attachment.filename
        content_url = latest_attachment.content

        logger.info(
            "Downloading most recent attachment",
            extra={
                "issue_key": issue_key,
                "url": _sanitize_url(content_url),
                "attachment_created": latest_attachment.created,
            },
        )

        output_path = output_dir / filename
        success = self._download_file_with_retry(content_url, output_path)
        if success:
            return output_path

        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _download_file_with_retry(
        self,
        url: str,
        output_path: Path,
        auth: tuple[str, str] | None = None,
        session: requests.Session | None = None,
    ) -> bool:
        """Helper method to download a file with retries."""
        start = time.monotonic()
        http_client = session if session is not None else self.session

        # When using a custom session, it carries its own auth.
        # If an explicit auth tuple is provided, we use it (e.g. for secure links).
        kwargs: dict[str, bool | tuple[float, int] | tuple[str, str]] = {
            "stream": True,
            "timeout": (3.05, 300),
        }
        if auth is not None:
            kwargs["auth"] = auth

        response = http_client.get(url, **kwargs)
        duration_ms = int((time.monotonic() - start) * 1000)

        _check_retryable(response)

        if response.status_code == 200:
            max_bytes = int(os.getenv("JIVE_MAX_ATTACHMENT_MB", "250")) * 1024 * 1024
            downloaded_bytes = 0
            try:
                exceeded_size = False
                with open(output_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > max_bytes:
                            exceeded_size = True
                            break
                        _ = f.write(chunk)

                if exceeded_size:
                    logger.error(
                        "Download exceeded maximum allowed size",
                        extra={
                            "url": _sanitize_url(url),
                            "max_mb": os.getenv("JIVE_MAX_ATTACHMENT_MB", "250"),
                        },
                    )
                    response.close()
                    output_path.unlink(missing_ok=True)
                    return False

                return True
            except Exception as e:
                logger.error("Failed writing downloaded chunk to disk", exc_info=e)
                output_path.unlink(missing_ok=True)
                raise
        else:
            logger.error(
                "Failed to download file content",
                extra={
                    "url": _sanitize_url(url),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return False

    def download_from_secure_link(
        self, url: str, output_dir: Path, filename: str = "secure_dataset.xlsx"
    ) -> Path | None:
        """Downloads the dataset from a provided secure link using optional Basic Auth."""
        logger.info(
            "Downloading from secure link",
            extra={"url": _sanitize_url(url)},
        )

        parsed_url = urllib.parse.urlparse(url)

        ALLOWED_DOMAINS: frozenset[str] = frozenset(
            filter(None, os.getenv("ALLOWED_DOMAINS", "NOT PROVIDED").split(","))
        )

        if not ALLOWED_DOMAINS:
            logger.error(
                "SSRF Protection: ALLOWED_DOMAINS is empty — blocking all secure link"
                + " downloads (fail-closed)",
                extra={"url": _sanitize_url(url)},
            )
            return None
        if parsed_url.scheme != "https" or parsed_url.netloc not in ALLOWED_DOMAINS:
            logger.error(
                "SSRF Protection: URL domain not in allowed list",
                extra={
                    "url": _sanitize_url(url),
                    "domain": parsed_url.netloc,
                    "allowed": list(ALLOWED_DOMAINS),
                },
            )
            return None

        output_path = output_dir / filename
        success = self._download_file_with_retry(url, output_path, auth=self.secure_link_auth)
        if success:
            return output_path
        return None
