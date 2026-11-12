import tempfile
import time
from pathlib import Path
from typing import override

import fastexcel
from azure.storage.blob import BlobServiceClient
from azure.storage.blob._shared.response_handlers import ResourceNotFoundError
from jira.models import IssueAttachment
from jira.proforma_parser import ProformaParser
from worker_base.base import BaseWorker, QueueMessage
from worker_base.dataset_utils import download_dataset
from worker_base.models import JiraSubmissionPayload

from .config import get_settings
from .logs import get_logger

settings = get_settings()
logger = get_logger("jive-file-mover.log")


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

                if dataset_path is not None:
                    file_directory = self.file_to_parquet(dataset_path, tmp_path)
                    self.upload_files(file_directory)

                    total_ms = int((time.monotonic() - start_time) * 1000)
                    self.logger.info(
                        "Job completed",
                        extra={"issue_key": payload.issue_key, "duration_ms": total_ms},
                    )
            else:
                raise ValueError("Failed to resolve issue ID from key.")

    def file_to_parquet(self, dataset: Path, directory: Path):
        local_path = directory / dataset.stem
        Path(local_path).mkdir(parents=True, exist_ok=True)
        excel_file = fastexcel.read_excel(dataset)
        all_sheets = excel_file.sheet_names
        for sheet_name in all_sheets:
            try:
                excel_sheet_df = excel_file.load_sheet(
                    sheet_name, whitespace_as_null=True, skip_whitespace_tail_rows=True
                ).to_polars()

                excel_sheet_df.write_parquet(local_path / f"{sheet_name}.parquet")
            except Exception as e:
                self.logger.error(
                    "Failed to save sheet as parquet",
                    exc_info=e,
                )

        return local_path

    def upload_files(self, directory: str | Path):
        blob_client = BlobServiceClient.from_connection_string(
            conn_str=settings.queue_connection_string
        )
        container_client = blob_client.get_container_client(
            container=settings.storage_container_name
        )

        try:
            self.logger.info("Getting container properties...")
            _ = container_client.get_container_properties()
        except ResourceNotFoundError:
            self.logger.info(
                "Container not found, creating it...",
                extra={"container": settings.storage_container_name},
            )
            container_client.create_container()

        files = Path(directory).glob("*.parquet")
        for file in files:
            try:
                with open(file=file, mode="rb") as data:
                    blob_client = container_client.upload_blob(
                        name=file.name, data=data, overwrite=True
                    )
            except Exception as e:
                self.logger.error(
                    "Failed to upload file to blob storage.",
                    exc_info=e,
                    extra={"file_name": file.name},
                )


def main():
    worker = Validator("file_mover", "File mover", settings.queue_name)
    worker.work()


if __name__ == "__main__":
    main()
