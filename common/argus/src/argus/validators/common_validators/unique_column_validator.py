from typing import override

import polars as pl

from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base import SheetClassification
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult


class UniqueColumnCheck(BaseValidator):
    @property
    @override
    def name(self) -> str:
        return "UniqueColumnCheck"

    def __init__(self, schema: BaseDatasetSchema):
        self.schema: BaseDatasetSchema = schema

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if any expected unique columns contain any
        non unique values across relevant sheets.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        duplicated_ids_df: pl.DataFrame = pl.DataFrame(
            [
                pl.Series("value", [], dtype=pl.String),
                pl.Series("count", [], dtype=pl.UInt32),
                pl.Series("sheet", [], dtype=pl.String),
                pl.Series("column", [], dtype=pl.String),
            ]
        )

        for sheet in self.schema.loaded_sheets:
            if sheet.classification == SheetClassification.RAW_DATA_SHEET:
                continue
            unique_columns = sheet.get_unique_columns()
            if not unique_columns:
                continue

            loaded_sheet_info = data.get_loaded_sheet(sheet.standard_name)

            if loaded_sheet_info:
                for column in unique_columns:
                    mapped_column = loaded_sheet_info.get_column_map(column.standard_name)
                    if mapped_column is not None:
                        unique_duplicated_rows_df = (
                            loaded_sheet_info.data.filter(
                                loaded_sheet_info.data.select(
                                    mapped_column.data_column_name
                                ).is_duplicated()
                            )
                            .select(pl.col(mapped_column.data_column_name).cast(pl.String))
                            .rename({mapped_column.data_column_name: "value"})
                            .group_by("value")
                            .having(pl.len() > 1)
                            .len("count")
                        )
                        if unique_duplicated_rows_df.height > 0:
                            # store for output
                            unique_duplicated_rows_df = (
                                unique_duplicated_rows_df.unique().with_columns(
                                    pl.lit(loaded_sheet_info.data_sheet_name).alias("sheet"),
                                    pl.lit(mapped_column.data_column_name).alias("column"),
                                )
                            )
                            duplicated_ids_df = pl.concat(
                                [duplicated_ids_df, unique_duplicated_rows_df]
                            )
        if duplicated_ids_df.height > 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "unique_column_validator.non_unique",
                        count=duplicated_ids_df.select(pl.col("count").sum()).item(),
                    ),
                    severity=SeverityLevel.ERROR,
                    details=duplicated_ids_df.to_dict(as_series=False),
                )
            )

        return results
