from typing import override

import polars as pl

from ...loaders.base import DataSheetMap
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base import SchemaColumnMap
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import get_data_loaded_columns, get_data_loaded_sheets


class MandatoryColumnsCheck(BaseValidator):
    @property
    @override
    def name(self) -> str:
        return "MandatoryColumnsCheck"

    def __init__(self, schema: BaseDatasetSchema):
        self.schema: BaseDatasetSchema = schema

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if any expected mandatory columns are missing
        across relevant sheets.

        Also checks if unique columns are missing.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """

        def _get_loaded_columns(schema_columns: list[SchemaColumnMap], loaded_sheet: DataSheetMap):
            search_items = {key.standard_name: loaded_sheet for key in schema_columns}
            result, _ = get_data_loaded_columns(search_items, self.name)
            if result is not None:
                result.sheet_name = loaded_sheet.data_sheet_name

            return result

        def _process_results(
            results: list[ValidationResult],
            severity: SeverityLevel,
            message_key: str,
            item_type: str,
        ):
            column_dict: list[dict[str, str]] = []

            for item in results:
                if item.details is None:
                    column_dict.append(
                        {
                            "sheet_name": item.sheet_name if item.sheet_name is not None else "",
                            "column_name": item.column_name if item.column_name is not None else "",
                            "required": "Yes"
                            if severity == SeverityLevel.ERROR
                            else "Check if required",
                        }
                    )
                else:
                    for _, d_columns in item.details.items():
                        for d_column in d_columns:
                            column_dict.append(
                                {
                                    "sheet_name": item.sheet_name
                                    if item.sheet_name is not None
                                    else "",
                                    "column_name": d_column,
                                    "required": "Yes"
                                    if severity == SeverityLevel.ERROR
                                    else "Check if required",
                                }
                            )

            column_df = pl.DataFrame(column_dict).to_dict(as_series=False)
            result = ValidationResult(
                rule=self.name,
                message=self._(message_key, count=len(results), item_type=item_type),
                severity=severity,
                details=column_df,
            )
            return result

        results: list[ValidationResult] = []
        results_required: list[ValidationResult] = []
        results_optional: list[ValidationResult] = []

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=self.schema.get_loaded_sheets_standard_names(required=True),
            rule=self.name,
            check_data=False,
        )
        # if optional sheets have been loaded, check their columns
        _, data_loaded_sheets_optional = get_data_loaded_sheets(
            data=data,
            sheet_names=self.schema.get_loaded_sheets_standard_names(required=False),
            rule=self.name,
            check_data=False,
        )

        if data_loaded_sheets_optional:
            data_loaded_sheets.update(data_loaded_sheets_optional)

        if result is not None:
            if result.details is None:
                result.details = {"missing_sheets": [result.sheet_name]}

            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "mandatory_column_validator.missing_item",
                        count=len(result.details["missing_sheets"]),
                        item_type="sheets",
                    ),
                    severity=SeverityLevel.ERROR,
                    details=result.details,
                )
            )

            return results

        for sheet, loaded_sheet in data_loaded_sheets.items():
            # get all the columns expected for the sheet

            schema_sheet = self.schema.get_schema_sheet(sheet)
            # sheet is checked above
            assert schema_sheet is not None

            required_columns = [column for column in schema_sheet.columns if column.required]
            optional_columns = [column for column in schema_sheet.columns if not column.required]

            if required_columns:
                result = _get_loaded_columns(required_columns, loaded_sheet)
                if result is not None:
                    results_required.append(result)

            if optional_columns:
                result = _get_loaded_columns(optional_columns, loaded_sheet)
                if result is not None:
                    results_optional.append(result)

        if results_required:
            result = _process_results(
                results_required,
                SeverityLevel.ERROR,
                "mandatory_column_validator.missing_item",
                item_type="columns",
            )
            results.append(result)

        if results_optional:
            result = _process_results(
                results_optional,
                SeverityLevel.WARNING,
                "mandatory_column_validator.optional_columns",
                item_type="",
            )
            results.append(result)

        return results
