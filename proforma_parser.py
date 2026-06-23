import os
import requests
import logging
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from logger import get_logger
from jira_client import JiraAPIError, _check_retryable

logger = get_logger("jive.proforma_parser")

class ProformaParser:
    def __init__(self, session: requests.Session, auth: tuple, base_url: str):
        self.session = session
        self.auth = auth
        self.base_url = base_url
        self.cloud_id: Optional[str] = None
        
        self.dataset_type_label = os.getenv("PROFORMA_DATASET_TYPE_LABEL", "Dataset type")
        self.repo_label = os.getenv("PROFORMA_REPO_LABEL", "IMPACT Repository")

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

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
        
        response = self.session.get(url, auth=self.auth, timeout=(3.05, 15))
        _check_retryable(response)
        response.raise_for_status()
        
        self.cloud_id = response.json()["cloudId"]
        logger.info("Atlassian Cloud ID cached successfully", extra={"cloud_id": self.cloud_id})
        return self.cloud_id

    def get_answers(self, issue_id: str) -> dict[str, str]:
        """Return {label: answer_text} for all answered questions on the submitted ProForma form."""
        try:
            cloud_id = self._get_cloud_id()
        except Exception as exc:
            logger.warning("Could not fetch Atlassian Cloud ID for ProForma", exc_info=exc)
            return {}

        url = f"https://api.atlassian.com/jira/forms/cloud/{cloud_id}/issue/{issue_id}/form"
        logger.info("Fetching ProForma forms list for issue", extra={"issue_id": issue_id, "url": url})
        
        try:
            response = self.session.get(url, auth=self.auth, headers=self.headers, timeout=(3.05, 15))
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
            
            detail_response = self.session.get(form_detail_url, auth=self.auth, headers=self.headers, timeout=(3.05, 15))
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
                    value = ", ".join(choice_map.get(cid, "").strip() for cid in choice_ids if choice_map.get(cid, "").strip())
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
