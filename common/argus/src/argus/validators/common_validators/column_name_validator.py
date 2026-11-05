from typing import override

import polars as pl

from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.options import COLUMN_NAME_VALIDATOR_PATTERN


class ColumnNameCheck(BaseValidator):
    """Check column names are variables instead of labels."""

    def __init__(self, ignore_sheets: list[str] | None = None):
        """
        Args:
            ignore_sheets (list[str] | None, optional): List of schema sheets to ignore during.
                Defaults to "choices" and "survey" if None is specefied.
        """
        self.ignore_sheets: list[str] = (
            ignore_sheets
            if ignore_sheets is not None
            else [settings.CHOICES_SHEET_NAME, settings.SURVEY_SHEET_NAME]
        )

    @property
    @override
    def name(self) -> str:
        return "ColumnNameCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Check column names are variables instead of labels.

        This is done through regex matching that checks if there
        are any characters other than:
        - A-Z
        - a-z
        - 0-9
        - . or _ or - or / or \\

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: list of validation errors
        """
        results: list[ValidationResult] = []

        match_records: list[dict[str, str]] = []

        for sheet in data.loaded_sheets:
            if sheet.schema_sheet_name in self.ignore_sheets:
                continue
            matches = list(filter(COLUMN_NAME_VALIDATOR_PATTERN.search, sheet.data.columns))
            if matches:
                match_records.extend(
                    [
                        {
                            "sheet": sheet.data_sheet_name,
                            "columns": item,
                        }
                        for item in matches
                    ]
                )

        if match_records:
            column_match_df = pl.DataFrame(match_records)
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "column_name_validator.labels",
                        count=column_match_df.select(pl.col("sheet")).unique().height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=column_match_df.to_dict(as_series=False),
                )
            )

        return results
