from typing import override

from ...common.list_matching import filter_list
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult


class MissingSheetsCheck(BaseValidator):
    @property
    @override
    def name(self) -> str:
        return "MissingSheetsCheck"

    def __init__(self, schema: BaseDatasetSchema):
        self.schema: BaseDatasetSchema = schema

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if any expected sheets are missing
        across a dataset.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        expected_sheets = [
            sheet.standard_name for sheet in self.schema.loaded_sheets if sheet.required
        ]
        expected_sheets.extend(
            [sheet.standard_name for sheet in self.schema.unloaded_sheets if sheet.required]
        )

        optional_sheets = [
            sheet.standard_name for sheet in self.schema.loaded_sheets if not sheet.required
        ]
        optional_sheets.extend(
            [sheet.standard_name for sheet in self.schema.unloaded_sheets if not sheet.required]
        )

        # get keys
        provided_sheets = data.get_loaded_sheet_mapped_names()
        provided_sheets.extend(data.get_unloaded_sheet_mapped_names())

        missing_sheets = filter_list(expected_sheets, provided_sheets)
        optional_missing_sheets = filter_list(optional_sheets, provided_sheets)

        if missing_sheets:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        key="missing_sheets_validator.missing_sheets", count=len(missing_sheets)
                    ),
                    severity=SeverityLevel.ERROR,
                    details={"missing_sheets": missing_sheets},
                )
            )

        if optional_missing_sheets:
            if "sampling_info" in optional_missing_sheets:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._("missing_sheets_validator.sampling_info"),
                        sheet_name="sampling_info",
                        severity=SeverityLevel.WARNING,
                        details={"optional_sheets": ["sampling_info"]},
                    )
                )
            optional_missing_sheets = filter_list(optional_missing_sheets, ["sampling_info"])
            if optional_missing_sheets:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            key="missing_sheets_validator.optional_missing_sheets",
                            count=len(optional_missing_sheets),
                        ),
                        severity=SeverityLevel.WARNING,
                        details={"optional_sheets": optional_missing_sheets},
                    )
                )

        return results
