from pathlib import Path
from typing import override

import polars as pl

from ...loaders.base_excel_loader import ExcelLoaderData
from ...validators.base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_column,
    get_data_loaded_columns,
    get_data_loaded_sheets,
)


class JMMIColumnDataCheck(BaseValidator):
    def __init__(
        self,
        meb_analysis_sheet: str = "meb_analysis",
        mfs_analysis_sheet: str = "mfs_analysis",
        clean_data_sheet: str = "clean_data",
        country_column: str = "country",
        round_column: str = "round",
        month_column: str = "month",
        year_column: str = "year",
    ):
        """

        Args:
            meb_analysis_sheet (str, optional):  Defaults to "meb_analysis".
            mfs_analysis_sheet (str, optional):  Defaults to "mfs_analysis".
            clean_data_sheet (str, optional):  Defaults to "clean_data".
            country_column (str, optional):  Defaults to "country".
            round_column (str, optional):  Defaults to "round".
            month_column (str, optional):  Defaults to "month".
            year_column (str, optional):  Defaults to "year".

        """

        self.meb_analysis_sheet: str = meb_analysis_sheet
        self.mfs_analysis_sheet: str = mfs_analysis_sheet
        self.clean_data_sheet: str = clean_data_sheet
        self.country_column: str = country_column
        self.round_column: str = round_column
        self.month_column: str = month_column
        self.year_column: str = year_column

    @property
    @override
    def name(self) -> str:
        return "JMMIColumnDataCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float | Path
    ) -> list[ValidationResult]:
        """Validates column data required for JMMI datasets.

        This checks the following rules
        - The "country" column must contain 3 uppercase characters
            (note: this could be expanded to check the value against
             the country list stored in schema configs)
        - The "round" column must start with "country", contain
            "month" and end with "year".
            eg: "SSD_JMMI_March_2026"

        Args:
            data (ExcelLoaderData): Excel data to validate

        Returns:
            list[ValidationResult]: list of validation results
        """

        results: list[ValidationResult] = []

        results_df = pl.DataFrame(
            [
                pl.Series("sheet", [], dtype=pl.String),
                pl.Series("column", [], dtype=pl.String),
                pl.Series("value", [], dtype=pl.String),
                pl.Series("rows_affected", [], dtype=pl.Int32),
                pl.Series("issue", [], dtype=pl.String),
            ]
        )

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.clean_data_sheet, self.meb_analysis_sheet, self.mfs_analysis_sheet],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        for sheet_name, sheet_data in data_loaded_sheets.items():
            # D004 - check country values
            result, country_loaded_column = get_data_loaded_column(
                sheet_data, self.country_column, self.name
            )

            if result is not None:
                results.append(result)
            else:
                assert country_loaded_column is not None

                invalid_country_df = (
                    sheet_data.data.filter(
                        (pl.col(country_loaded_column.data_column_name).str.len_chars() != 3)
                        | (
                            pl.col(country_loaded_column.data_column_name).str.to_uppercase()
                            != pl.col(country_loaded_column.data_column_name)
                        )
                    )
                    .select(pl.col(country_loaded_column.data_column_name).alias("value"))
                    .group_by("value")
                    .len("rows_affected")
                )

                if invalid_country_df.height > 0:
                    invalid_country_issue_message = self._(
                        "jmmi_data_validator.data_issues.invalid_country.issue",
                        column=country_loaded_column.data_column_name,
                    )
                    invalid_country_df = invalid_country_df.with_columns(
                        [
                            pl.lit(sheet_name).alias("sheet"),
                            pl.lit(country_loaded_column.data_column_name).alias("column"),
                            pl.lit(invalid_country_issue_message).alias("issue"),
                        ]
                    )

                    results_df = pl.concat([results_df, invalid_country_df], how="diagonal_relaxed")

            # D005 round column must correctly contain country, year and month columns
            if sheet_name == self.clean_data_sheet:
                round_columns_to_get = {
                    column: sheet_data
                    for column in [
                        self.country_column,
                        self.year_column,
                        self.month_column,
                        self.round_column,
                    ]
                }

                result, round_loaded_columns = get_data_loaded_columns(
                    round_columns_to_get, self.name
                )

                if result is not None:
                    results.append(result)
                else:
                    invalid_round_issue_message = self._(
                        "jmmi_data_validator.data_issues.invalid_round.issue",
                        main_column=round_loaded_columns[self.round_column].data_column_name,
                        start_column=round_loaded_columns[self.country_column].data_column_name,
                        contain_column=round_loaded_columns[self.month_column].data_column_name,
                        end_column=round_loaded_columns[self.year_column].data_column_name,
                    )
                    invalid_round_df = (
                        sheet_data.data.filter(
                            # First 3 characters must equal country column
                            (
                                pl.col(round_loaded_columns[self.country_column].data_column_name)
                                != pl.col(
                                    round_loaded_columns[self.round_column].data_column_name
                                ).str.slice(length=3, offset=0)
                            )
                            |
                            # last 4 characters must equal year column
                            (
                                pl.col(
                                    round_loaded_columns[self.year_column].data_column_name
                                ).cast(pl.String)
                                != pl.col(
                                    round_loaded_columns[self.round_column].data_column_name
                                ).str.slice(-4)
                            )
                            |
                            # must contain month column
                            (
                                ~pl.col(
                                    round_loaded_columns[self.round_column].data_column_name
                                ).str.contains(
                                    pl.col(round_loaded_columns[self.month_column].data_column_name)
                                )
                            )
                        )
                        .select(
                            (
                                pl.lit("column: '")
                                + pl.col(round_loaded_columns[self.round_column].data_column_name)
                                + pl.lit(
                                    f"', {round_loaded_columns[self.country_column].data_column_name}: '"  # noqa: E501
                                )
                                + pl.col(round_loaded_columns[self.country_column].data_column_name)
                                + pl.lit(
                                    f"', {round_loaded_columns[self.month_column].data_column_name}: '"  # noqa: E501
                                )
                                + pl.col(round_loaded_columns[self.month_column].data_column_name)
                                + pl.lit(
                                    f"', {round_loaded_columns[self.year_column].data_column_name}: '"  # noqa: E501
                                )
                                + pl.col(round_loaded_columns[self.year_column].data_column_name)
                                + pl.lit("'")
                            ).alias("value")
                        )
                        .group_by("value")
                        .len("rows_affected")
                        .with_columns(
                            pl.lit(sheet_name).alias("sheet"),
                            pl.lit(round_loaded_columns[self.round_column].data_column_name).alias(
                                "column"
                            ),
                            pl.lit(invalid_round_issue_message).alias("issue"),
                        )
                    )

                    if invalid_round_df.height > 0:
                        results_df = pl.concat(
                            [
                                results_df,
                                invalid_round_df,
                            ],
                            how="diagonal_relaxed",
                        )

        if results_df.height > 0:
            issue_row_count = (
                results_df.select(pl.col("rows_affected").sum()).to_series().to_list()[0]
            )
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._("jmmi_data_validator.data_issues", count=issue_row_count),
                    severity=SeverityLevel.ERROR,
                    details=results_df.to_dict(as_series=False),
                )
            )

        return results
