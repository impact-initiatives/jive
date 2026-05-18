import os
import re
import time
import tempfile
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
        self.base_url = os.getenv("JIRA_BASE_URL", "https://reach-initiative.atlassian.net").rstrip("/")

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

        #IMPACT Repository WP Credentials
        self.repo_username = os.getenv("REPO_USERNAME")
        self.repo_password = os.getenv("REPO_PASSWORD")
        self.repo_session = None

        #ProForma matching labels
        self.proforma_repo_label = os.getenv("PROFORMA_REPO_LABEL", "IMPACT Repository")
        self.proforma_dataset_type_label = os.getenv("PROFORMA_DATASET_TYPE_LABEL", "Dataset type")

        self.cloud_id = None
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
            try:
                attachments_data = response.json()
                if attachments_data and isinstance(attachments_data, list):
                    return attachments_data[0].get("content")
            except Exception:
                pass
            return True
        else:
            logger.error(
                "Failed to upload attachment",
                extra={"issue_key": issue_key, "status_code": response.status_code},
            )
            return None

    def get_service_desk_id(self, project_key: str) -> Optional[str]:
        """Fetch the Service Desk ID associated with a project key."""
        url = f"{self.base_url}/rest/servicedeskapi/servicedesk/{project_key}"
        try:
            response = self.session.get(url, auth=self.auth, headers=self.headers, timeout=15)
            _check_retryable(response)
            if response.status_code == 200:
                return response.json().get("id")
            else:
                logger.warning("Service Desk lookup returned non-200 status", extra={"project_key": project_key, "status_code": response.status_code})
        except Exception as e:
            logger.warning(f"Could not fetch Service Desk ID for project {project_key}", exc_info=e)
        return None

    def upload_public_jsm_attachment(self, issue_key: str, project_key: str, file_path: Path) -> bool:
        """Uploads an attachment publicly to a Jira Service Management ticket so it is visible directly on the portal."""
        # 1. Fetch Service Desk ID
        service_desk_id = self.get_service_desk_id(project_key)
        if not service_desk_id:
            logger.error("Failed to upload JSM attachment: could not resolve service desk ID for project", extra={"project_key": project_key})
            return False

        # 2. Upload temporary file
        upload_url = f"{self.base_url}/rest/servicedeskapi/servicedesk/{service_desk_id}/attachTemporaryFile"
        headers = {
            "X-Atlassian-Token": "no-check",
            "Accept": "application/json",
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
                logger.info("Uploading temporary JSM attachment", extra={"issue_key": issue_key, "service_desk_id": service_desk_id})
                response = self.session.post(upload_url, headers=headers, auth=self.auth, files=files, timeout=(5, 120))
                _check_retryable(response)
                
                if response.status_code != 201:
                    logger.error("Failed to upload temporary JSM attachment", extra={"issue_key": issue_key, "status_code": response.status_code})
                    return False
                
                temp_attachments = response.json().get("temporaryAttachments", [])
                if not temp_attachments:
                    logger.error("Temporary JSM attachment response contained no attachments", extra={"issue_key": issue_key})
                    return False
                
                temp_attachment_id = temp_attachments[0].get("temporaryAttachmentId")
                logger.info("Temporary JSM attachment uploaded successfully", extra={"issue_key": issue_key, "temp_id": temp_attachment_id})
        except Exception as e:
            logger.error("Failed to upload temporary JSM attachment", exc_info=e, extra={"issue_key": issue_key})
            return False

        # 3. Attach temporary file to request publicly
        attach_url = f"{self.base_url}/rest/servicedeskapi/request/{issue_key}/attachment"
        attach_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "temporaryAttachmentIds": [temp_attachment_id],
            "public": True
        }
        
        try:
            logger.info("Confirming public JSM attachment on request", extra={"issue_key": issue_key})
            response = self.session.post(attach_url, headers=attach_headers, auth=self.auth, json=payload, timeout=(5, 30))
            _check_retryable(response)
            
            if response.status_code == 201:
                logger.info("Successfully attached file publicly to JSM portal request", extra={"issue_key": issue_key})
                return True
            else:
                logger.error("Failed to attach file publicly to JSM request", extra={"issue_key": issue_key, "status_code": response.status_code})
                return False
        except Exception as e:
            logger.error("Failed to attach file publicly to JSM request", exc_info=e, extra={"issue_key": issue_key})
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
            extra={"issue_key": issue_key, "url": content_url, "attachment_created": latest_attachment.get("created")}
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
    def _download_file_with_retry(self, url: str, output_path: Path, auth: Optional[tuple] = None, session: Optional[requests.Session] = None) -> bool:
        """Helper method to download a file with retries."""
        start = time.monotonic()
        http_client = session if session is not None else self.session
        
        #When using a custom session, we do not pass auth since session carries its own (e.i. WP cookies)
        kwargs = {"stream": True, "timeout": (5, 300)}
        if session is None and auth is not None:
            kwargs["auth"] = auth

        response = http_client.get(url, **kwargs)
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _get_cloud_id(self) -> str:
        """Fetch and cache the Atlassian Cloud ID (required by ProForma Cloud API)."""
        if self.cloud_id is not None:
            return self.cloud_id

        url = f"{self.base_url}/_edge/tenant_info"
        logger.info("Fetching Atlassian Cloud ID", extra={"url": url})
        
        response = self.session.get(url, auth=self.auth, timeout=15)
        _check_retryable(response)
        response.raise_for_status()
        
        self.cloud_id = response.json()["cloudId"]
        logger.info("Atlassian Cloud ID cached successfully", extra={"cloud_id": self.cloud_id})
        return self.cloud_id

    def get_proforma_answers(self, issue_id: str) -> dict[str, str]:
        """Return {label: answer_text} for all answered questions on the submitted ProForma form."""
        try:
            cloud_id = self._get_cloud_id()
        except Exception as exc:
            logger.warning("Could not fetch Atlassian Cloud ID for ProForma", exc_info=exc)
            return {}

        url = f"https://api.atlassian.com/jira/forms/cloud/{cloud_id}/issue/{issue_id}/form"
        logger.info("Fetching ProForma forms list for issue", extra={"issue_id": issue_id, "url": url})
        
        try:
            response = self.session.get(url, auth=self.auth, headers=self.headers, timeout=15)
            _check_retryable(response)
            if response.status_code in (403, 404):
                logger.warning("ProForma API returned status code, forms might not be configured/enabled", 
                               extra={"issue_id": issue_id, "status_code": response.status_code})
                return {}
            response.raise_for_status()
            
            forms = response.json()
            submitted = [f for f in forms if f.get("submitted")]
            if not submitted:
                logger.warning("No submitted ProForma form found for issue", extra={"issue_id": issue_id})
                return {}

            # Fetch detailed answers of the first submitted form
            form_id = submitted[0]["id"]
            form_detail_url = f"{url}/{form_id}"
            logger.info("Fetching ProForma form details", extra={"issue_id": issue_id, "form_id": form_id})
            
            detail_response = self.session.get(form_detail_url, auth=self.auth, headers=self.headers, timeout=15)
            _check_retryable(detail_response)
            detail_response.raise_for_status()
            
            form = detail_response.json()
            questions = form.get("design", {}).get("questions", {})
            answers = form.get("state", {}).get("answers", {})

            result = {}
            for qid, q in questions.items():
                label = q.get("label", "")
                question_key = q.get("questionKey", "")
                answer = answers.get(qid, {})

                # Choices take priority over text for radio/checkbox types
                choice_ids = answer.get("choices", [])
                if choice_ids:
                    choice_map = {c["id"]: c["label"] for c in q.get("choices", [])}
                    value = choice_map.get(choice_ids[0], "").strip()
                else:
                    value = answer.get("text", "").strip()

                if not value:
                    continue
                if label:
                    result[label] = value
                if question_key:
                    result[question_key] = value
            
            logger.info("Successfully parsed ProForma answers", 
                        extra={"issue_id": issue_id, "fields_parsed": list(result.keys())})
            return result
        except Exception as e:
            logger.error("Failed to parse ProForma answers", exc_info=e, extra={"issue_id": issue_id})
            return {}

    def _get_repo_session(self) -> requests.Session:
        """Return an authenticated Session for the IMPACT Repository (WordPress cookie auth)."""
        if self.repo_session is not None:
            return self.repo_session

        if not self.repo_username or not self.repo_password:
            raise EnvironmentError("REPO_USERNAME and REPO_PASSWORD environment variables must be set")

        base_url = "https://repository.impact-initiatives.org"
        logger.info("Creating authenticated session for IMPACT Repository", extra={"username": self.repo_username.split("@")[0]})
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        
        # Prime testcookie
        session.get(f"{base_url}/wp-login.php", timeout=15)
        
        # Submit login form
        response = session.post(
            f"{base_url}/wp-login.php",
            data={
                "log": self.repo_username,
                "pwd": self.repo_password,
                "wp-submit": "Log In",
                "redirect_to": f"{base_url}/resources/",
                "testcookie": "1",
            },
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()
        
        self.repo_session = session
        logger.info("Authenticated session created for IMPACT Repository successfully")
        return session

    def _scrape_excel_url(self, page_url: str) -> Optional[str]:
        """Scrape a repository page to find the direct .xlsx download link."""
        logger.info("Scraping IMPACT Repository page for Excel link", extra={"page_url": page_url})
        try:
            session = self._get_repo_session()
            response = session.get(page_url, timeout=15)
            response.raise_for_status()
            
            match = re.search(
                r'href="(https://repository\.impact-initiatives\.org/[^"]+\.xlsx?)"',
                response.text,
            )
            if match:
                excel_url = match.group(1)
                logger.info("Excel download link found on repository page", extra={"excel_url": excel_url})
                return excel_url
            
            logger.warning("No .xlsx or .xls link found on repository page", extra={"page_url": page_url})
            return None
        except Exception as e:
            logger.error("Failed to scrape Excel URL from repository page", exc_info=e, extra={"page_url": page_url})
            return None

    def get_issue_id(self, issue_key: str) -> Optional[str]:
        """Fetch the internal issue ID (integer string) using the issue key."""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}?fields=id"
        logger.info("Resolving issue ID from key", extra={"issue_key": issue_key, "url": url})
        try:
            response = self.session.get(url, auth=self.auth, headers=self.headers, timeout=15)
            _check_retryable(response)
            response.raise_for_status()
            issue_id = response.json().get("id")
            logger.info("Resolved issue ID successfully", extra={"issue_key": issue_key, "issue_id": issue_id})
            return issue_id
        except Exception as e:
            logger.error("Failed to resolve issue ID from key", exc_info=e, extra={"issue_key": issue_key})
            return None

    def resolve_dataset(self, issue_key: str, output_dir: Path, issue_id: Optional[str] = None, attachments: Optional[list] = None, secure_link: Optional[str] = None) -> Optional[Path]:
        """Orchestrates resolving the dataset using a fallback/priority strategy:
        
        1. Direct Attachment (Highest Priority): Check for any .xlsx/.xls files attached directly to the Jira ticket.
        2. IMPACT Repository (Secondary): Parse the ProForma form to extract the IMPACT Repository page URL and scrape/download.
        3. Webhook/Fallback Secure Link (Tertiary): Direct download from custom secure links.
        """
        logger.info("Starting dataset resolution workflow", extra={"issue_key": issue_key})
        
        # ── 1. Direct Attachment (Highest Priority) ──
        dataset_path = self.download_proforma_attachment(issue_key, output_dir, attachments=attachments)
        if dataset_path:
            logger.info("Successfully resolved dataset from Jira attachment", 
                        extra={"issue_key": issue_key, "resolved_filename": dataset_path.name})
            return dataset_path

        # ── 2. IMPACT Repository via ProForma (Secondary) ──
        logger.info("No direct attachment found, attempting ProForma form parsing", extra={"issue_key": issue_key})
        
        resolved_issue_id = issue_id or self.get_issue_id(issue_key)
        if resolved_issue_id:
            proforma_answers = self.get_proforma_answers(resolved_issue_id)
            
            # Find label matching the repo label pattern (case-insensitive)
            page_url = None
            needle = self.proforma_repo_label.lower()
            for label, val in proforma_answers.items():
                if needle in label.lower():
                    page_url = val
                    break
                    
            if page_url:
                logger.info("IMPACT Repository URL found in ProForma answers", extra={"issue_key": issue_key, "page_url": page_url})
                excel_url = self._scrape_excel_url(page_url)
                if excel_url:
                    filename = excel_url.rstrip("/").split("/")[-1] or f"{issue_key}.xlsx"
                    output_path = output_dir / filename
                    
                    logger.info("Downloading scraped Excel file from Repository", extra={"issue_key": issue_key, "url": excel_url})
                    session = self._get_repo_session()
                    success = self._download_file_with_retry(excel_url, output_path, auth=None, session=session)
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
            dataset_path = self.download_from_secure_link(secure_link, output_dir)
            if dataset_path:
                logger.info("Successfully resolved dataset from fallback secure link", 
                            extra={"issue_key": issue_key, "resolved_filename": dataset_path.name})
                return dataset_path

        return None
