import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import override

import fastexcel
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from jira.models import IssueAttachment
from jira.proforma_parser import ProformaParser
from worker_base.base import BaseWorker, QueueMessage
from worker_base.dataset_utils import download_dataset
from worker_base.models import JiraSubmissionPayload

from .config import get_settings
from .logs import get_logger

settings = get_settings()
logger = get_logger("jive-file-mover.log")


class FileMover(BaseWorker):
    def __init__(self, logger_name: str, description: str, queue_name: str) -> None:
        super().__init__(logger_name, description, queue_name)

        blob_client = BlobServiceClient.from_connection_string(
            conn_str=settings.queue_connection_string
        )
        self.container_client = blob_client.get_container_client(
            container=settings.storage_container_name
        )

        try:
            self.container_client.create_container()
        except ResourceExistsError:
            self.logger.info("Container already exists, continuing.")

    @override
    def process_message(self, msg: QueueMessage, payload: JiraSubmissionPayload):
        """Processes a single Jira file moving job where excel file sheets are saved
        as parquet files and uploaded to blob storage."""
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
            proforma_answers = (
                proforma.get_answers(resolved_issue_id) if resolved_issue_id is not None else {}
            )

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
                    self.logger.info(
                        "Saving sheets to parquet",
                        extra={"issue_key": payload.issue_key},
                    )
                    file_directory = self.file_to_parquet(dataset_path, tmp_path)

                    self.logger.info(
                        "Uploading files to storage",
                        extra={"issue_key": payload.issue_key},
                    )
                    self.upload_files(file_directory)

                    total_ms = int((time.monotonic() - start_time) * 1000)
                    self.logger.info(
                        "Job completed",
                        extra={"issue_key": payload.issue_key, "duration_ms": total_ms},
                    )
            else:
                raise ValueError("Failed to resolve issue ID from key.")

    def file_to_parquet(self, dataset: Path, directory: Path) -> Path:
        """Saves all excel sheets as parquet files. No filtering on sheet names
            is done.

        Args:
            dataset (Path): File path for the excel file
            directory (Path): Base directory for the parquet files

        Raises:
            RuntimeError: If any sheets fail to be written as parquet files

        Returns:
            Path: Output directory for parquet files
        """
        local_path = directory / dataset.stem
        Path(local_path).mkdir(parents=True, exist_ok=True)
        excel_file = fastexcel.read_excel(dataset)
        all_sheets = excel_file.sheet_names
        failures: list[tuple[str, Exception]] = []

        for sheet_name in all_sheets:
            try:
                excel_sheet_df = excel_file.load_sheet(
                    sheet_name, whitespace_as_null=True, skip_whitespace_tail_rows=True
                ).to_polars()

                # remove characters in sheet names that could cause issues when used as file names
                safe_sheet_name = re.sub(r"[^\w\-]+", "_", sheet_name).strip("_") or "unnamed"
                if safe_sheet_name != sheet_name:
                    self.logger.info(
                        f"Sheet '{sheet_name}' changed to '{safe_sheet_name}' for output filename.",
                    )
                excel_sheet_df.write_parquet(local_path / f"{safe_sheet_name}.parquet")
            except Exception as e:
                self.logger.error(
                    "Failed to save sheet as parquet",
                    exc_info=e,
                )
                failures.append((sheet_name, e))

        if failures:
            raise RuntimeError(
                f"Failed to convert {len(failures)} of {len(all_sheets)} sheets: "
                f"{[name for name, _ in failures]}"
            )

        return local_path

    def upload_files(self, directory: str | Path):
        """Uploads a directory of parquet files to blob storage

        Args:
            directory (str | Path): Dirctory containing parquet files

        Raises:
            FileNotFoundError: If no files are in the directory
            RuntimeError: If any files fail to upload
        """
        failures: list[tuple[str, Exception]] = []

        upload_directory = f"{settings.base_upload_directory}/{Path(directory).name}/"

        def _upload_file(file: Path) -> None:
            with open(file=file, mode="rb") as data:
                self.container_client.upload_blob(
                    name=f"{upload_directory}{file.name}",
                    data=data,
                    overwrite=True,
                )

        files = list(Path(directory).glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"No parquet files found in {directory}")

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_upload_file, file): file for file in files}

            for future in as_completed(futures):
                file = futures[future]
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(
                        "Failed to upload file to blob storage.",
                        exc_info=e,
                        extra={"file_name": file.name},
                    )
                    failures.append((file.name, e))

        if failures:
            raise RuntimeError(
                f"Failed to upload {len(failures)} of {len(futures)} files: "
                f"{[name for name, _ in failures]}"
            )


def main():
    worker = FileMover("file_mover", "File mover", settings.queue_name)
    worker.work()


if __name__ == "__main__":
    main()
