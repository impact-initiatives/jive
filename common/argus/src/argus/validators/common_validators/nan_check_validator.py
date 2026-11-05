from typing import override

import polars as pl

from ...common.list_matching import filter_list
from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import get_data_loaded_sheets, get_data_sheet_ids


class NaNDataCheck(BaseValidator):
    """Checks columns for invalid numeric values like NaN and -999.
    Invalid values are stored in the config file.

    """

    def __init__(self, schema: BaseDatasetSchema, check_sheets: list[str] | None = None) -> None:
        """
        Args:
            schema (BaseDatasetSchema): schema for the dataset
            sheets (List[str], optional): list of sheets to be checked.
                Defaults to ['clean_data'].
        """
        self.check_sheets: list[str] = check_sheets if check_sheets is not None else ["clean_data"]
        self.schema: BaseDatasetSchema = schema

    @property
    @override
    def name(self) -> str:
        return "NaNDataCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks columns for invalid numeric values like NaN and -999.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        output_difference_df = pl.DataFrame(
            [
                pl.Series("uuid", [], dtype=pl.String),
                pl.Series("sheet", [], dtype=pl.String),
                pl.Series("column", [], dtype=pl.String),
                pl.Series("value", [], dtype=pl.String),
            ]
        )

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data, sheet_names=self.check_sheets, rule=self.name
        )

        if result is not None:
            results.append(result)
            return results

        result, sheet_ids = get_data_sheet_ids(self.schema, data_loaded_sheets, self.name)
        if result:
            results.extend(result)
            return results

        for sheet in self.check_sheets:
            nan_value_expressions = []
            filtered_columns = filter_list(
                data_loaded_sheets[sheet].data.columns,
                settings.IGNORE_COLUMNS_FOR_VALIDATION,
            )
            filtered_df = data_loaded_sheets[sheet].data.select(filtered_columns)

            # build expression to find possible invalid values or NaNs
            for column in filtered_columns:
                expression = pl.any_horizontal(
                    (
                        (
                            pl.col(column).is_nan()
                            | (
                                pl.col(column)
                                .cast(pl.Float64, strict=False)
                                .is_in(settings.NANCHECK_NUMERIC_VALUES)
                            )
                        )
                        if filtered_df.schema[column].is_float()
                        else False
                        | (
                            pl.col(column)
                            .cast(pl.Float64, strict=False)
                            .is_in(settings.NANCHECK_NUMERIC_VALUES)
                        )
                        if filtered_df.schema[column].is_integer()
                        else False | (pl.col(column).is_in(settings.NANCHECK_STRING_VALUES))
                        if filtered_df.schema[column] == pl.String
                        else pl.lit(False)
                    ).alias(f"is_{column}_nan_value")
                )
                nan_value_expressions.append(expression)

            # get a df that has nan/invalid data in a row
            nan_df = filtered_df.with_columns(nan_value_expressions)
            has_nan = pl.any_horizontal(
                [pl.col(f"is_{column}_nan_value") for column in filtered_columns]
            )
            nan_only_df = nan_df.filter(has_nan)

            # create df of only invalid data
            # transform data from a wide format to a long format and join to flags.
            # this allows for filtering nan values in a single operation
            if not nan_only_df.is_empty():
                id_column = sheet_ids[sheet][0].data_column_name

                # unvpvot values
                values_df = nan_only_df.unpivot(
                    index=[id_column],
                    on=filtered_columns,
                    variable_name="column",
                    value_name="value",
                )

                # unpivot flags. Extract question name from flag column name
                flags_df = nan_only_df.unpivot(
                    index=[id_column],
                    on=[f"is_{c}_nan_value" for c in filtered_columns],
                    variable_name="flag_column_name",
                    value_name="is_changed",
                ).with_columns(
                    pl.col("flag_column_name")
                    .str.replace("^is_", "", literal=False)
                    .str.replace("_nan_value$", "", literal=False)
                    .alias("column")
                )

                # join all together
                # Filter only rows where the NaN flag is True
                merged_df = values_df.join(flags_df, on=[id_column, "column"], how="inner").filter(
                    pl.col("is_changed")
                )

                # get the valies
                output_df = merged_df.select(
                    [
                        pl.col(id_column).cast(pl.String).alias("uuid"),
                        pl.lit(sheet).alias("sheet"),
                        pl.col("column"),
                        pl.col("value").cast(pl.String).alias("value"),
                    ]
                )
                # concat results to those from previous sheets
                output_difference_df = pl.concat([output_difference_df, output_df])

        if output_difference_df.height > 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "nan_check_validator.nan_values", count=output_difference_df.height
                    ),
                    severity=SeverityLevel.ERROR,
                    details=output_difference_df.to_dict(as_series=False),
                )
            )

        return results
