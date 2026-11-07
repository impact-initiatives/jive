from typing import cast, override

import polars as pl

from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base import SheetClassification
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult


class EmptyColumnCheck(BaseValidator):
    @property
    @override
    def name(self) -> str:
        return "EmptyColumnCheck"

    def __init__(self, schema: BaseDatasetSchema):
        self.schema: BaseDatasetSchema = schema

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if any columns contain empty values
        across relevant sheets and columns.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        empty_values_df: pl.DataFrame = pl.DataFrame(
            [
                pl.Series("sheet", [], dtype=pl.String),
                pl.Series("column", [], dtype=pl.String),
                pl.Series("empty_values", [], dtype=pl.Int32),
            ]
        )

        for sheet in self.schema.loaded_sheets:
            if sheet.classification == SheetClassification.RAW_DATA_SHEET:
                continue
            not_empty_columns = sheet.get_not_empty_columns()
            if not not_empty_columns:
                continue

            loaded_sheet_info = data.get_loaded_sheet(sheet.standard_name)

            if loaded_sheet_info:
                for column in not_empty_columns:
                    mapped_column = loaded_sheet_info.get_column_map(column.standard_name)
                    if mapped_column is not None:
                        sheet_empty_values_df = (
                            loaded_sheet_info.data.select(
                                pl.col(mapped_column.data_column_name).cast(pl.String)
                            )
                            .filter(
                                pl.any_horizontal(
                                    pl.col(mapped_column.data_column_name)
                                    .fill_null("")
                                    .str.strip_chars()
                                    .is_in(["", None])
                                )
                            )
                            .group_by(pl.col(mapped_column.data_column_name))
                            .len("empty_values")
                        )
                        if sheet_empty_values_df.height > 0:
                            sheet_empty_values_df = sheet_empty_values_df.select(
                                [pl.col("empty_values").sum()]
                            ).with_columns(
                                pl.lit(loaded_sheet_info.data_sheet_name).alias("sheet"),
                                pl.lit(mapped_column.data_column_name).alias("column"),
                            )

                            empty_values_df = pl.concat(
                                [sheet_empty_values_df, empty_values_df], how="diagonal_relaxed"
                            )

        if empty_values_df.height > 0:
            empty_rows = cast(
                int, (empty_values_df.select(pl.col("empty_values").sum()).to_series().to_list()[0])
            )
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "empty_column_validator.empty_values",
                        count=empty_rows,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=empty_values_df.to_dict(as_series=False),
                )
            )

        return results
