from typing import override

import polars as pl

from ...common.list_matching import duplicate_list_items
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult


class DuplicateSheetMatchCheck(BaseValidator):
    """Checks to see if a schema sheet was matched to multiple excel sheets."""

    def __init__(self, schema: BaseDatasetSchema):
        self.schema: BaseDatasetSchema = schema

    @property
    @override
    def name(self) -> str:
        return "DuplicateSheetMatchCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if a schema sheet was matched to multiple excel sheets.

        Args:
            data (ExcelLoaderData): excel data

        Returns:
            List[ValidationResult]: list of validation errors.
        """
        results: list[ValidationResult] = []

        provided_sheets = data.get_loaded_sheet_mapped_names()
        provided_sheets.extend(data.get_unloaded_sheet_mapped_names())
        # duplicates should be a unique list
        duplicates = duplicate_list_items(provided_sheets)
        matches: list[dict[str, str | list[str]]] = []

        if duplicates:
            for item in duplicates:
                schema_sheet = self.schema.get_schema_sheet(item)
                if schema_sheet and schema_sheet.matching_term:
                    # matching on terms can match a schema sheet to multiple excel sheets
                    # which is intended so ignore as part of this check
                    continue

                matched_sheets = data.get_sheet_matches(item)
                sheet_names = [name.data_sheet_name for name in matched_sheets]
                matches.extend([{"sheet": item, "matches": sheet_names}])

            if matches:
                matches_df = pl.DataFrame(matches)
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            "duplicate_sheet_match_validator.duplicate_sheets",
                            count=matches_df.select(pl.col("sheet")).unique().height,
                        ),
                        severity=SeverityLevel.ERROR,
                        details=matches_df.to_dict(as_series=False),
                    )
                )

        return results
