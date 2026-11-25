import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastexcel import CalamineCellError
from jive_logging.logger import get_logger

from ..config import settings
from ..loaders.base import DataSheetMap
from ..loaders.base_excel_loader import ExcelLoaderData
from ..loaders.excel_loader import ExcelLoader, ExcelSource
from ..locales.il8n import _, i18n
from ..models.base_dataset_schemas import BaseDatasetSchema
from ..models.dynamic_defined_schema import DynamicDefinedDataset
from ..models.dynamic_schema import DynamicDataset
from ..models.resolver import find_dataset_files
from ..orchestrator.output_models import MetadataModel, PipelineResponse, SummaryModel
from ..validators.base import (
    BaseValidator,
    SeverityLevel,
    ValidationResult,
    ValidatorResponse,
    ValidatorResult,
)

logger = get_logger("argus.orchestrator")

_BUCKET_PRECEDENCE: tuple[tuple[str, frozenset[SeverityLevel]], ...] = (
    ("admin_errors", frozenset({SeverityLevel.ADMIN_ERROR})),
    ("errors", frozenset({SeverityLevel.ERROR})),
    ("warnings", frozenset({SeverityLevel.WARNING})),
    ("info", frozenset({SeverityLevel.INFO})),
    ("admin_info", frozenset({SeverityLevel.ADMIN_INFO})),
)


class OrchestratorError(Exception):
    def __init__(self, details: list[ValidationResult]):
        self.details = details


class ValidationPipeline:
    def __init__(self):
        self.set_errors: set[SeverityLevel] = set([SeverityLevel.ADMIN_ERROR, SeverityLevel.ERROR])
        self.filename: str = ""

    @staticmethod
    def _source_filename(source: ExcelSource, override: str | None = None) -> str:
        """Resolve a display/log filename from any ExcelSource variant."""
        if override:
            return Path(override).name
        if isinstance(source, (Path, str)):
            return Path(source).name
        # file-like: open files, BytesIO with a name set, Streamlit UploadedFile, ...
        name = getattr(source, "name", None)
        if isinstance(name, str) and name:
            return Path(name).name
        return ""

    def _setup_schema(self, programme_type: str, output_type: str, locale: str):
        """Initialise schema and validators based on dataset type.

        Raises:
            ValueError: if dataset type not found.
        """
        schema_file_name = "schema.yaml"
        validator_file_name = "validators.yaml"
        result = find_dataset_files(
            root_directory=settings.schemas_directory,
            programme_type=programme_type,
            output_type=output_type,
            locale=locale,
            schema_file_name=schema_file_name,
            validator_file_name=validator_file_name,
        )

        if result:
            if result["programme_type"] != settings.FALLBACK_PROGRAMME:
                dataset = DynamicDefinedDataset(
                    schema_path=result[schema_file_name], validator_path=result[validator_file_name]
                )
            else:
                dataset = DynamicDataset(
                    schema_path=result[schema_file_name], validator_path=result[validator_file_name]
                )
        else:
            raise ValueError(
                f"Unable to find files for {schema_file_name} and {validator_file_name} for "
                + f"programme '{programme_type}', output '{output_type}'"
                + f" and locale '{locale}'."
            )

        return dataset

    def run_all(
        self,
        filepath: ExcelSource,
        programme_type: str,
        output_type: str,
        locale: str = settings.FALLBACK_LOCALE,
    ) -> PipelineResponse:
        """_summary_

        Args:
            filepath (Path): The excel filepath.
            programme_type (str): programme type: jmmi, other
            output_type (str): type of output: dataset, analysis
            locale (str, optional): language to use for validation messages, if supported.
                Defaults to "en".

        Returns:
            dict[str, Any]: json results
        """
        locale = locale.lower()
        token = i18n.set_locale(locale)
        programme_type = programme_type.lower()
        output_type = output_type.lower()
        self.filename = self._source_filename(filepath)
        logger.info("Running the validation pipeline.", extra={"file": self.filename})
        results = self._run(
            filepath=filepath,
            programme_type=programme_type,
            output_type=output_type,
            locale=locale,
        )
        i18n.reset_locale(token)
        logger.info("Compiling validation results.", extra={"file": self.filename})
        return self._compile_results(
            results=results,
            filepath=filepath,
            programme_type=programme_type,
            output_type=output_type,
        )

    def _run(
        self,
        filepath: ExcelSource,
        programme_type: str,
        output_type: str,
        locale: str,
    ) -> list[ValidatorResponse]:
        """Orchestrator for the dataset validation pipeline.

        Args:
            filepath (Path): The excel filepath.

        Returns:
            list[ValidationResult]: validation results.

        """
        all_responses: list[ValidatorResponse] = []
        orchestrator_response = ValidatorResponse(name="ArgusOrchestrator")

        orchestrator_results: list[ValidationResult] = []

        # load the initial schema and validator list
        try:
            dataset = self._setup_schema(
                programme_type=programme_type,
                output_type=output_type,
                locale=locale,
            )

            if dataset.schema.programme_type != programme_type:
                orchestrator_results.append(
                    ValidationResult(
                        message=f"No schema for '{programme_type}' '{output_type}' was"
                        + " found. Falling back to"
                        + f" '{dataset.schema.programme_type}' '{dataset.schema.output_type}'.",
                        severity=SeverityLevel.WARNING,
                    )
                )
                logger.warning(
                    f"No dataset schema for '{programme_type}' '{output_type}' was found"
                    + ". Falling back to"
                    + f" '{dataset.schema.programme_type}' '{dataset.schema.output_type}'.",
                    extra={"file": self.filename},
                )

        except Exception as e:
            orchestrator_results.append(
                ValidationResult(
                    message=f"Error getting the YAML dataset config files: {str(e)}",
                    severity=SeverityLevel.ADMIN_ERROR,
                )
            )
            logger.exception(
                "Error getting the YAML dataset config files.",
                extra={
                    "file": self.filename,
                    "programme_type": programme_type,
                    "output_type": output_type,
                    "schemas_directory": settings.schemas_directory.resolve(),
                },
            )
            orchestrator_response.result = ValidatorResult.ORCHESTRATOR_ERROR
            orchestrator_response.details.extend(orchestrator_results)
            return [orchestrator_response]

        # pre-validate the schema. checks for duplicate sheet/column
        # names etc

        try:
            logger.info(
                "Validating schema.",
                extra={
                    "file": self.filename,
                    "programme_type": dataset.schema.programme_type,
                    "output_type": dataset.schema.output_type,
                },
            )
            validation_errors = dataset.validate_schema_item_names()

            if validation_errors:
                orchestrator_results.extend(validation_errors)
                logger.error(
                    f"Validating schema for '{programme_type}' '{output_type}' failed.",
                    extra={"validation errors": validation_errors, "file": self.filename},
                )
                orchestrator_response.result = ValidatorResult.ORCHESTRATOR_ERROR
                orchestrator_response.details.extend(orchestrator_results)
                return [orchestrator_response]
        except Exception as e:
            orchestrator_results.append(
                ValidationResult(
                    message=f"Schema validation encountered an error: {str(e)}",
                    severity=SeverityLevel.ADMIN_ERROR,
                    details=vars(dataset.schema),
                )
            )
            logger.exception(
                "Schema validation encountered an error.",
                extra={
                    "file": self.filename,
                    "programme_type": dataset.schema.programme_type,
                    "output_type": dataset.schema.output_type,
                },
            )
            orchestrator_response.result = ValidatorResult.ORCHESTRATOR_ERROR
            orchestrator_response.details.extend(orchestrator_results)
            return [orchestrator_response]

        # load the excel data
        try:
            logger.info("Loading and matching Excel data.", extra={"file": self.filename})
            loader = ExcelLoader(dataset.schema)
            dataset.data, excel_results = loader.load(
                filepath,
                load_all_sheets=dataset.schema.programme_type == settings.FALLBACK_PROGRAMME,
            )

            if excel_results:
                orchestrator_response.details.extend(excel_results)

            orchestrator_response.details.append(
                ValidationResult(
                    message="Data mapping after data load.",
                    severity=SeverityLevel.ADMIN_INFO,
                    details=self._excel_loader_to_dict(dataset.data),
                )
            )
        except CalamineCellError as ce:
            orchestrator_results.append(
                ValidationResult(
                    message=_(
                        "validation_pipeline.calamine_cell_error", file=self.filename, error=str(ce)
                    ),
                    severity=SeverityLevel.ERROR,
                )
            )
            logger.exception(
                "Loading of the excel file encountered a CalamineCellError.",
                extra={"file": self.filename},
            )
            orchestrator_response.result = ValidatorResult.ORCHESTRATOR_ERROR
            orchestrator_response.details.extend(orchestrator_results)
            return [orchestrator_response]
        except Exception as e:
            orchestrator_results.append(
                ValidationResult(
                    message=f"Loading of the excel file '{self.filename}'"
                    + f" encountered an error: {str(e)}",
                    severity=SeverityLevel.ADMIN_ERROR,
                )
            )
            logger.exception(
                "Loading of the excel file encountered an error.", extra={"file": self.filename}
            )
            orchestrator_response.result = ValidatorResult.ORCHESTRATOR_ERROR
            orchestrator_response.details.extend(orchestrator_results)
            return [orchestrator_response]

        logger.info(
            "Building schema and validators.",
            extra={
                "file": self.filename,
                "programme_type": dataset.schema.programme_type,
                "output_type": dataset.schema.output_type,
            },
        )
        results: list[ValidationResult] = dataset.process_data()
        if results:
            orchestrator_results.extend(results)

        orchestrator_results.append(
            ValidationResult(
                message="Data mapping after dynamic data matching.",
                severity=SeverityLevel.ADMIN_INFO,
                details=self._excel_loader_to_dict(dataset.data),
            )
        )

        orchestrator_results.append(
            ValidationResult(
                message=f"Schema for dataset '{programme_type}' '{output_type}' and"
                + f" file '{filepath}'",
                severity=SeverityLevel.ADMIN_INFO,
                details=vars(dataset.schema),
            )
        )

        # run each of the validators for the dataset.
        logger.info(
            "Running validation rules.",
            extra={
                "file": self.filename,
                "programme_type": dataset.schema.programme_type,
                "output_type": dataset.schema.output_type,
            },
        )
        for validator in dataset.validators:
            try:
                validator_response = validator.validate(dataset.data)

                if not self._check_errors(validator_response, self.set_errors):
                    validator_response.result = ValidatorResult.PASSED
                all_responses.append(validator_response)
            except Exception as e:
                all_responses.append(
                    ValidatorResponse(
                        name=validator.name,
                        details=[
                            ValidationResult(
                                message=f"Validator '{validator.name}' encountered an error:"
                                + f" {traceback.format_exc()} {e}",
                                severity=SeverityLevel.ADMIN_ERROR,
                                details=self._get_validator_params(validator),
                            )
                        ],
                        result=ValidatorResult.ORCHESTRATOR_ERROR,
                    )
                )
                logger.exception(
                    f"Validator '{validator.name}' encountered an error.",
                    extra={"file": self.filename, "validator": validator.name},
                )

        if self._check_errors(orchestrator_response, self.set_errors):
            orchestrator_response.result = ValidatorResult.ORCHESTRATOR_ERROR

        all_responses.append(orchestrator_response)
        return all_responses

    def _check_errors(
        self, response: ValidatorResponse, errors: list[SeverityLevel] | set[SeverityLevel]
    ):
        return any(result.severity in errors for result in response.details)

    def _bucket_for_response(self, response: ValidatorResponse) -> str:

        severities = {detail.severity for detail in response.details}
        for bucket, levels in _BUCKET_PRECEDENCE:
            if severities & levels:
                return bucket
        return "passed"

    def _compile_results(
        self,
        results: list[ValidatorResponse],
        programme_type: str,
        output_type: str,
        filepath: ExcelSource,
    ) -> PipelineResponse:
        """Compile validator responses into the typed pipeline output."""
        buckets: dict[str, list[ValidatorResponse]] = {
            name: [] for name, _ in _BUCKET_PRECEDENCE
        } | {"passed": []}

        for response in results:
            self._truncate_details(response.details)
            buckets[self._bucket_for_response(response)].append(response)

        severity_counts = Counter(d.severity for response in results for d in response.details)

        return PipelineResponse(
            success=not (buckets["errors"] or buckets["admin_errors"]),
            summary=SummaryModel(
                passed=severity_counts[SeverityLevel.PASSED],
                errors=severity_counts[SeverityLevel.ERROR],
                warnings=severity_counts[SeverityLevel.WARNING],
                info=severity_counts[SeverityLevel.INFO],
                admin_errors=severity_counts[SeverityLevel.ADMIN_ERROR],
                admin_info=severity_counts[SeverityLevel.ADMIN_INFO],
            ),
            metadata=MetadataModel(
                # TODO: this is the requested programme_type, not the fallback one
                programme_type=programme_type,
                output_type=output_type,
                validation_date=datetime.now(UTC).isoformat(timespec="seconds"),
                file_name=self.filename,
            ),
            **buckets,
        )

    def _truncate_details(self, results: list[ValidationResult]) -> None:
        """Apply the details-threshold limit in place."""
        if settings.LIMIT_DETAILS_THRESHOLD <= 0:
            return
        for result in results:
            if not result.details:
                continue
            was_truncated = False
            for key, value in result.details.items():
                if isinstance(value, list) and len(value) > settings.LIMIT_DETAILS_THRESHOLD:
                    result.details[key] = value[: settings.LIMIT_DETAILS_THRESHOLD]
                    was_truncated = True
            if was_truncated:
                result.message = f"{result.message} " + _(
                    "validation_pipeline.limit_details", count=settings.LIMIT_DETAILS_THRESHOLD
                )

    def _get_validator_params(self, validator: BaseValidator) -> dict[str, Any]:
        """Get validator paramaters for logs but exclude schema."""
        return {
            key: value
            for key, value in vars(validator).items()
            if not isinstance(value, BaseDatasetSchema)
        }

    def _excel_loader_to_dict(self, excel_loader: ExcelLoaderData) -> dict[str, Any]:
        """Convert ExcelLoaderData to dict, excluding data and column fields."""

        def data_sheet_map_to_dict(data_sheet: DataSheetMap) -> dict[str, Any]:
            return {
                "schema_sheet_name": data_sheet.schema_sheet_name,
                "data_sheet_name": data_sheet.data_sheet_name,
                "column_map": data_sheet.column_map,
            }

        return {
            "loaded_sheets": [
                data_sheet_map_to_dict(sheet) for sheet in excel_loader.loaded_sheets
            ],
            "unloaded_sheets": [
                data_sheet_map_to_dict(sheet) for sheet in excel_loader.unloaded_sheets
            ],
            "unexpected_sheets": excel_loader.unexpected_sheets,
        }
