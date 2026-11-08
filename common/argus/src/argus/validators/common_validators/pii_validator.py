from typing import override

import polars as pl

from ...common.list_matching import filter_list, match_list_to_list
from ...config import settings
from ...loaders.base import DataColumnMap
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import get_data_sheet_id
from ..helpers.options import PII_PATTERN_EXPRESSIONS, PII_PATTERNS, get_pii_columns


class PiiDataCheck(BaseValidator):
    """Checks all the sheets for possible PII Data"""

    def __init__(self, schema: BaseDatasetSchema, ignore_sheets: list[str] | None = None):
        """
        Args:
            schema (BaseDatasetSchema): dataset schema
            ignore_sheets (list[str] | None, optional): List of schema sheets to ignore during.
                Defaults to "choices" and "survey" if None is specefied.
        """
        self.schema: BaseDatasetSchema = schema
        self.ignore_sheets: list[str] = (
            ignore_sheets
            if ignore_sheets is not None
            else [settings.CHOICES_SHEET_NAME, settings.SURVEY_SHEET_NAME]
        )

    @property
    @override
    def name(self) -> str:
        return "PiiDataCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """This performs two sets of checks

        First: checks to see if any pii columns are present across relevant sheets.
            Possible pii columns are currently stored in models/config.
            Fuzzy matching is also optionally performed.

        Second: performs regex matching on sheets for possible pii data.
            Currently matching is fairly simple and limited to:
            - emails
            - possible phone numbers: must start with a 0 or +
                and not be a decimal. This is a limited implementaion.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []
        pii_columns = get_pii_columns()

        match_records: list[dict[str, str]] = []

        for sheet in data.loaded_sheets:
            if sheet.schema_sheet_name in self.ignore_sheets:
                continue
            filtered_df = sheet.data.select(
                filter_list(sheet.data.columns, settings.IGNORE_COLUMNS_FOR_VALIDATION)
            )
            # scan column names
            literal_matches, fuzzy_matched_values = match_list_to_list(
                filtered_df.columns, pii_columns, True
            )

            if literal_matches:
                match_records.extend(
                    [
                        {
                            "sheet": sheet.data_sheet_name,
                            "column": item,
                            "match_type": "literal",
                            "matched_value": item,
                        }
                        for item in literal_matches
                    ]
                )

            if fuzzy_matched_values:
                match_records.extend(
                    [
                        {
                            "sheet": sheet.data_sheet_name,
                            "column": item.schema_name,
                            "match_type": "fuzzy",
                            "matched_value": str(item.matches),
                        }
                        for item in fuzzy_matched_values
                    ]
                )

            # scan column data
            _, id_column = get_data_sheet_id(sheet.data_sheet_name, self.schema, sheet, self.name)

            if not id_column:
                id_column = DataColumnMap(
                    data_column_name="row_index", schema_column_name="row_index"
                )
                melted_df = filtered_df.with_row_index(id_column.data_column_name).unpivot(
                    index=id_column.data_column_name,
                    variable_name="column",
                    value_name="value",
                )
            else:
                id_column = id_column[0]
                # unpivot to make showing the results easier
                melted_df = filtered_df.unpivot(
                    index=id_column.data_column_name,
                    variable_name="column",
                    value_name="value",
                )

            # add expression columns
            melted_df = melted_df.with_columns(PII_PATTERN_EXPRESSIONS)
            # build match conditions
            match_conditions = [pl.col(name=f"match_{t}").is_not_null() for t in PII_PATTERNS]

            # apply conditions and filter the data
            any_match_condition = pl.any_horizontal(match_conditions)
            filtered_df = melted_df.filter(any_match_condition)

            match_cols = [f"match_{t}" for t in PII_PATTERNS]

            # format results for output
            final_df = filtered_df.unpivot(
                index=[id_column.data_column_name, "column"],
                on=match_cols,
                variable_name="pii_type_raw",
                value_name="matched_value",
            )
            # unpivot will add extra rows so remove those that havent actually matched
            final_df = final_df.filter(pl.col("matched_value").is_not_null())

            final_df = (
                final_df.with_columns(
                    pl.col("pii_type_raw").str.replace("match_", "").alias("pii_type")
                )
                .select([id_column.data_column_name, "column", "pii_type", "matched_value"])
                .filter(
                    (
                        (pl.col("matched_value").str.len_chars() > settings.MIN_PHONE_LENGTH)
                        & (pl.col("pii_type") == "phone")
                    )
                    | (pl.col("pii_type") != "phone")
                )
                .with_columns(pl.lit(sheet.data_sheet_name).alias("sheet"))
            )

            if final_df.height > 0:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._("pii_validator.pii_data", sheet=sheet.data_sheet_name),
                        severity=SeverityLevel.WARNING,
                        sheet_name=sheet.data_sheet_name,
                        details=final_df.to_dict(as_series=False),
                    )
                )
        if match_records:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._("pii_validator.pii_columns", count=len(match_records)),
                    severity=SeverityLevel.WARNING,
                    details=pl.DataFrame(match_records).to_dict(as_series=False),
                )
            )

        return results
