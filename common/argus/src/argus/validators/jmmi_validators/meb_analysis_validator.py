from pathlib import Path
from typing import override

import polars as pl

from ...loaders.base_excel_loader import ExcelLoaderData
from ...validators.base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_sheets,
)


class JMMIMebAnalysisCheck(BaseValidator):
    def __init__(
        self,
        meb_analysis_sheet: str = "meb_analysis",
        clean_data_sheet: str = "clean_data",
        numeric_column_suffix_check_list: list[str] | None = None,
    ):

        self.meb_analysis_sheet: str = meb_analysis_sheet
        self.clean_data_sheet: str = clean_data_sheet
        self.numeric_column_suffix_check_list: list[str] = (
            numeric_column_suffix_check_list
            if numeric_column_suffix_check_list is not None
            else ["currency", "official", "parallel", "year"]
        )

    @property
    @override
    def name(self) -> str:
        return "JMMIMebAnalysisCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float | Path
    ) -> list[ValidationResult]:
        """Validates the column names for JMMI meb_analysis sheets.

        JMMI datasets have standardised naming conventions. This checks the follwoing rules:
        - there are at least two columns ending in "_local_currency" and "usd_xrate_official"
        - numeric variables should only end "_currency", "official","parallel", "year”
            - also checks if there are non-numeric variables with these suffixes
        - (not implemented yet) if there are any columns with "exchange_rate_buy_usd_" or
        "exchange_rate_sell_usd_" in clean_data then meb should have columns with
        usd_xrate_official and usd_xrate_parallel

        Args:
            data (ExcelLoaderData): data (ExcelLoaderData): data to be validated

        Returns:
            list[ValidationResult]: a list of validation results
        """

        results: list[ValidationResult] = []
        # C003
        expected_suffixes_found: int = 2

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.meb_analysis_sheet, self.clean_data_sheet],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        # C003: in the MEB tab there are at least 2 columns ending in
        # "_local_currency" and "usd_xrate_official"
        meb_analysis_columns = data_loaded_sheets[self.meb_analysis_sheet].data.columns
        local_currency_column_found = [
            column for column in meb_analysis_columns if "local_currency" in column
        ]
        usd_xrate_official_column_found = [
            column for column in meb_analysis_columns if "usd_xrate_official" in column
        ]

        if len(local_currency_column_found) < expected_suffixes_found:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_meb_analysis_validator.suffix_check",
                        count=len(local_currency_column_found),
                        no_expected=expected_suffixes_found,
                        expected_suffix="local_currency",
                        sheet=self.meb_analysis_sheet,
                    ),
                    severity=SeverityLevel.ERROR,
                )
            )

        if len(usd_xrate_official_column_found) < expected_suffixes_found:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_meb_analysis_validator.suffix_check",
                        count=len(usd_xrate_official_column_found),
                        no_expected=expected_suffixes_found,
                        expected_suffix="usd_xrate_official",
                        sheet=self.meb_analysis_sheet,
                    ),
                    severity=SeverityLevel.ERROR,
                )
            )

        # C005
        # columns with a numeric suffix
        meb_column_suffix_check_list_found = [
            column
            for column in meb_analysis_columns
            if any(
                suffix in column.split("_")[-1] for suffix in self.numeric_column_suffix_check_list
            )
        ]

        meb_numeric_columns = (
            data_loaded_sheets[self.meb_analysis_sheet].data.select(pl.selectors.numeric()).columns
        )

        # numeric columns without suffix
        meb_numeric_column_missing_suffix = [
            column
            for column in meb_numeric_columns
            if not any(
                suffix in column.split("_")[-1] for suffix in self.numeric_column_suffix_check_list
            )
        ]

        # columns with suffix but not numeric
        meb_non_numeric_column_with_suffix = [
            column
            for column in meb_column_suffix_check_list_found
            if column not in meb_numeric_columns
        ]

        if meb_numeric_column_missing_suffix:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_meb_analysis_validator.numeric_suffix_check",
                        count=len(meb_numeric_column_missing_suffix),
                        expected_suffixes=", ".join(
                            f"'{item}'" for item in self.numeric_column_suffix_check_list
                        ),
                        sheet=self.meb_analysis_sheet,
                    ),
                    severity=SeverityLevel.ERROR,
                    details={"numeric columns without suffix": meb_numeric_column_missing_suffix},
                )
            )

        if meb_non_numeric_column_with_suffix:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "jmmi_meb_analysis_validator.numeric_suffix_check_non_numeric_columns",
                        count=len(meb_non_numeric_column_with_suffix),
                        sheet=self.meb_analysis_sheet,
                    ),
                    severity=SeverityLevel.ERROR,
                    details={
                        "non-numeric column with numeric suffix": meb_non_numeric_column_with_suffix
                    },
                )
            )

        # C001 exchange rate columns
        # exchange_rate_column_check_list = ["exchange_rate_buy_usd", "exchange_rate_sell_usd"]
        # exchange_rate_columns = [
        #     column
        #     for column in data_loaded_sheets[self.clean_data_sheet].data.columns
        #     if any(suffix in column for suffix in exchange_rate_column_check_list)
        # ]

        # if exchange_rate_columns:
        #     meb_columns = [column for column in meb_analysis_columns if "meb" in column]
        #     meb_official_columns_missing = [column for column in meb_columns if
        # "usd_xrate_official" not in column]
        #     meb_parallel_columns_missing = [column for column in meb_columns if
        # "usd_xrate_parallel" not in column]

        #     if meb_columns:
        #         # meb_columns should be half
        #         if len(meb_official_columns_missing) > len(meb_columns) / 2:
        #             results.append(
        #             ValidationResult(
        #                 rule=self.name,
        #                 message=self._(
        #                     "jmmi_meb_analysis_validator.meb_official_columns_missing",
        #                     count=len(meb_official_columns_missing),
        #                     sheet=self.meb_analysis_sheet,
        #                     suffix = "usd_xrate_official"
        #                 ),
        #                 severity=SeverityLevel.ERROR,
        #                 details={
        #                     "columns missing usd_xrate_official suffix":
        #  meb_official_columns_missing
        #                 },
        #             )
        #         )

        #         if meb_parallel_columns_missing:
        #             results.append(
        #             ValidationResult(
        #                 rule=self.name,
        #                 message=self._(
        #                     "jmmi_meb_analysis_validator.meb_parallel_columns_missing",
        #                     count=len(meb_parallel_columns_missing),
        #                     sheet=self.meb_analysis_sheet,
        #                     suffix = "usd_xrate_parallel"
        #                 ),
        #                 severity=SeverityLevel.ERROR,
        #                 details={
        #                     "columns missing usd_xrate_parallel suffix":
        # meb_parallel_columns_missing
        #                 },
        #             )
        #         )
        #     else:
        #         results.append(
        #             ValidationResult(
        #                 rule=self.name,
        #                 message=self._(
        #                     "jmmi_meb_analysis_validator.no_meb_columns",
        #                     sheet=self.meb_analysis_sheet,
        #                 ),
        #                 severity=SeverityLevel.ERROR,

        #             )
        #         )

        return results
