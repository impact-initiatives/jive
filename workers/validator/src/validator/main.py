import tempfile
import time
from pathlib import Path
from typing import override

from jira.models import IssueAttachment
from jira.proforma_parser import ProformaParser
from worker_base.base import BaseWorker, QueueMessage
from worker_base.dataset_utils import download_dataset
from worker_base.models import JiraSubmissionPayload

from .config import get_settings
from .excel_exporter import export_response_to_excel
from .worker_utils import (
    check_idempotency,
    publish_results,
    resolve_context,
    run_validation,
)
from .logs import get_logger

settings = get_settings()
logger = get_logger("jive.validator")


class Validator(BaseWorker):
    @override
    def process_message(self, msg: QueueMessage, payload: JiraSubmissionPayload):
        """Processes a single Jira validation job."""
        self.logger.info(
            "Processing message",
            extra={"issue_key": payload.issue_key, "dequeue_count": msg.dequeue_count},
        )

        proforma = ProformaParser(self.jira_client.session)

        # Fetch attachments once — used for both idempotency and download
        attachments: list[IssueAttachment] | None = self.jira_client.get_attachments(
            payload.issue_key
        )

        if check_idempotency(payload, attachments):
            return

        start_time = time.monotonic()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Resolve issue ID once to reuse
            resolved_issue_id = self.jira_client.get_issue_id(payload.issue_key)
            proforma_answers = proforma.get_answers(resolved_issue_id) if resolved_issue_id else {}

            if resolved_issue_id is not None:
                dataset_path = download_dataset(
                    self.jira_client,
                    proforma,
                    payload,
                    tmp_path,
                    resolved_issue_id,
                    attachments,
                    proforma_answers,
                )

                repo_url, repo_action = resolve_context(
                    proforma, payload, resolved_issue_id, proforma_answers
                )
                if dataset_path is not None:
                    response = run_validation(dataset_path, payload)

                    duration_ms = int((time.monotonic() - start_time) * 1000)
                    self.logger.info(
                        "Pipeline completed",
                        extra={"issue_key": payload.issue_key, "duration_ms": duration_ms},
                    )

                    excel_report_path = (
                        tmp_path / f"JIVE_Validation_Report_{payload.issue_key}.xlsx"
                    )
                    export_response_to_excel(response, excel_report_path)

                    publish_results(
                        self.jira_client,
                        payload,
                        response,
                        excel_report_path,
                        repo_url,
                        repo_action,
                    )

                    total_ms = int((time.monotonic() - start_time) * 1000)
                    self.logger.info(
                        "Job completed",
                        extra={"issue_key": payload.issue_key, "duration_ms": total_ms},
                    )
            else:
                raise ValueError("Failed to resolve issue ID from key.")


def main():
    worker = Validator("validator", "File validator", settings.queue_name)
    worker.work()


if __name__ == "__main__":
    main()
