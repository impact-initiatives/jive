import logging

import requests
from requests.sessions import Session
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import get_settings
from ..jira.jira_client import JiraAPIError, check_retryable
from ..logger import get_logger
from .models import Form, FormDocument

logger = get_logger("jive.proforma_parser")
settings = get_settings()


class ProformaParser:
    def __init__(self, session: requests.Session, auth: tuple[str, str], base_url: str):
        self.session: Session = session
        self.auth: tuple[str, str] = auth
        self.base_url: str = base_url
        self.cloud_id: str | None = None

        self.dataset_type_label: str = settings.proforma_dataset_type_label
        self.repo_label: str = settings.proforma_repository_label

        self.headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (JiraAPIError, requests.exceptions.ConnectionError, requests.exceptions.Timeout)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _get_cloud_id(self) -> str:
        """Fetch and cache the Atlassian Cloud ID (required by ProForma Cloud API)."""
        if self.cloud_id is not None:
            return self.cloud_id

        url = f"{self.base_url}/_edge/tenant_info"
        logger.info("Fetching Atlassian Cloud ID", extra={"url": url})

        response = self.session.get(url, auth=self.auth, timeout=(3.05, 15))
        check_retryable(response)
        response.raise_for_status()

        self.cloud_id = response.json()["cloudId"]
        assert self.cloud_id is not None
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
        logger.info(
            "Fetching ProForma forms list for issue", extra={"issue_id": issue_id, "url": url}
        )

        try:
            response = self.session.get(
                url, auth=self.auth, headers=self.headers, timeout=(3.05, 15)
            )
            check_retryable(response)
            if response.status_code in (403, 404):
                logger.warning(
                    "ProForma API returned status code, forms might not be configured/enabled",
                    extra={"issue_id": issue_id, "status_code": response.status_code},
                )
                return {}
            response.raise_for_status()

            forms = [Form.model_validate(item) for item in response.json()]
            if not forms or not forms[0].submitted:
                logger.warning(
                    "No submitted ProForma form found for issue", extra={"issue_id": issue_id}
                )
                return {}

            # Fetch detailed answers of the first submitted form
            form_detail_url = f"{url}/{forms[0].id}"
            logger.info(
                "Fetching ProForma form details",
                extra={"issue_id": issue_id, "form_id": forms[0].id},
            )

            detail_response = self.session.get(
                form_detail_url, auth=self.auth, headers=self.headers, timeout=(3.05, 15)
            )
            check_retryable(detail_response)
            detail_response.raise_for_status()

            form = FormDocument.model_validate(detail_response.json())
            answers = form.state.answers

            result = {}
            for qid, q in form.design.questions.items():
                label = q.get("label", "")
                question_key = q.get("questionKey", "")
                answer = answers.get(qid, {})

                # Choices take priority over text for radio/checkbox types
                choice_ids = answer.get("choices", [])
                if choice_ids:
                    choice_map = {c["id"]: c["label"] for c in q.get("choices", [])}
                    value = ", ".join(
                        choice_map.get(cid, "").strip()
                        for cid in choice_ids
                        if choice_map.get(cid, "").strip()
                    )
                else:
                    value = answer.get("text", "").strip()

                if not value:
                    continue
                if label:
                    result[label] = value
                if question_key:
                    result[question_key] = value

            logger.info(
                "Successfully parsed ProForma answers",
                extra={"issue_id": issue_id, "fields_parsed": list(result.keys())},
            )
            return result
        except Exception as e:
            logger.error(
                "Failed to parse ProForma answers", exc_info=e, extra={"issue_id": issue_id}
            )
            return {}
