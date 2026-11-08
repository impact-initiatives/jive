from typing import override

import polars as pl

from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_columns,
    get_data_loaded_sheets,
    get_data_sheet_ids,
)
from ..helpers.schema_helpers import (
    get_schema_loaded_columns,
    get_schema_loaded_sheets,
    get_schema_process_values,
)


class DataTypeCheck(BaseValidator):
    """Checks that columns and column values are the correct datatype
    based on the kobo survey.
    """

    def __init__(
        self,
        schema: BaseDatasetSchema,
        survey_sheet: str = settings.SURVEY_SHEET_NAME,
        survey_type_column: str = "type",
        survey_name_column: str = "name",
        check_sheets: list[str] | None = None,
    ) -> None:
        """

        Args:
            schema (BaseDatasetSchema): dataset schema
            survey_sheet (str, optional): name of the kobo survey sheet in excel.
                Defaults to 'survey'.
            survey_type_column (str, optional): name of the type column in the
                kobo survey sheet. Defaults to 'type'.
            survey_name_column (str, optional): name of the name column in the
                kobo survey sheet. Defaults to 'name'.
            check_sheets (List, optional): schema sheet names to check.
                Defaults to ['clean_data'].
        """
        self.survey_sheet: str = survey_sheet
        self.check_sheets: list[str] = check_sheets if check_sheets is not None else ["clean_data"]
        self.survey_type_column: str = survey_type_column
        self.survey_name_column: str = survey_name_column
        self.schema: BaseDatasetSchema = schema
        self.process_value_map_name_numeric: str = "data_type_numeric_check"
        self.process_value_map_name_temporal: str = "data_type_temporal_check"

    @property
    @override
    def name(self) -> str:
        return "DataTypeCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks that columns and column values are the correct datatype
        based on the kobo survey.

        Currently checking numeric and temporal columns.

        Expects process_values to be present for the kobo_survey schema sheet
        in the type column to store both the numeric and temporal datatype names
        found in the kobo_survey type column

        if a column is the correct data type then its safe to assume that
        all the values are the correct datatype

        if the column is the incorrect data type then the values are checked.

        Args:
            data (ExcelLoaderData): excel data to validate

        Returns:
            List[ValidationResult]: list of validation errors
        """
        results: list[ValidationResult] = []
        # pre-validation

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.survey_sheet, *self.check_sheets],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, data_loaded_columns = get_data_loaded_columns(
            data={
                self.survey_type_column: data_loaded_sheets[self.survey_sheet],
                self.survey_name_column: data_loaded_sheets[self.survey_sheet],
            },
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, schema_loaded_sheets = get_schema_loaded_sheets(
            schema=self.schema, sheet_names=[self.survey_sheet], rule=self.name
        )

        if result is not None:
            results.append(result)
            return results

        result, schema_loaded_columns = get_schema_loaded_columns(
            data={
                self.survey_type_column: schema_loaded_sheets[self.survey_sheet],
                self.survey_name_column: schema_loaded_sheets[self.survey_sheet],
            },
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, schema_process_values = get_schema_process_values(
            data={
                self.survey_sheet: {
                    self.process_value_map_name_numeric: schema_loaded_columns[
                        self.survey_type_column
                    ],
                    self.process_value_map_name_temporal: schema_loaded_columns[
                        self.survey_type_column
                    ],
                },
            },
            rule=self.name,
        )

        if result:
            results.extend(result)
            return results

        search_items = {key: data_loaded_sheets[key] for key in self.check_sheets}
        result, data_id_columns = get_data_sheet_ids(
            schema=self.schema, data=search_items, rule=self.name
        )

        if result:
            results.extend(result)
            return results

        # get the columns that need checking
        numeric_columns = (
            data_loaded_sheets[self.survey_sheet]
            .data.filter(
                pl.col(data_loaded_columns[self.survey_type_column].data_column_name)
                .str.to_lowercase()
                .is_in(schema_process_values[self.process_value_map_name_numeric].values)
            )
            .select([data_loaded_columns[self.survey_name_column].data_column_name])
            .to_series()
            .str.to_lowercase()
            .to_list()
        )
        temporal_columns = (
            data_loaded_sheets[self.survey_sheet]
            .data.filter(
                pl.col(data_loaded_columns[self.survey_type_column].data_column_name)
                .str.to_lowercase()
                .is_in(schema_process_values[self.process_value_map_name_temporal].values)
            )
            .select([data_loaded_columns[self.survey_name_column].data_column_name])
            .to_series()
            .str.to_lowercase()
            .to_list()
        )

        for sheet in self.check_sheets:
            # # validate the sheet

            check_sheet_id_column = data_id_columns[sheet][0]

            # numeric check
            if numeric_columns:
                # check the data types of the data frame columns
                incorrect_data_type_columns = [
                    item
                    for item in numeric_columns
                    if item in data_loaded_sheets[sheet].data.columns
                    and not data_loaded_sheets[sheet].data.schema[item].is_numeric()
                ]

                if incorrect_data_type_columns:
                    # if there are dataframe columns with the incorrect data type
                    # then check the column values

                    # pivot the table to make the process easier
                    check_df = (
                        data_loaded_sheets[sheet]
                        .data.select(
                            [check_sheet_id_column.data_column_name] + incorrect_data_type_columns
                        )
                        .unpivot(
                            index=check_sheet_id_column.data_column_name,
                            variable_name="question",
                            value_name="value",
                        )
                    )
                    # find invalid values
                    # if the value cant be converted it will return null.
                    # this is used as a filter on the dataframe
                    incorrect_values_df = check_df.filter(pl.col("value").is_not_null()).filter(
                        pl.col("value").cast(pl.Float64, strict=False).is_null()
                    )

                    if incorrect_values_df.height > 0:
                        numeric_issue_message = self._(
                            "column_data_type_validator.numeric_check.issue"
                        )

                        incorrect_values_df = incorrect_values_df.with_columns(
                            pl.lit(sheet).alias("sheet"),
                            pl.lit(numeric_issue_message).alias("issue"),
                        )
                        results.append(
                            ValidationResult(
                                rule=self.name,
                                message=self._(
                                    "column_data_type_validator.numeric_check",
                                    count=incorrect_values_df.height,
                                    sheet=sheet,
                                ),
                                severity=SeverityLevel.ERROR,
                                sheet_name=sheet,
                                details=incorrect_values_df.to_dict(as_series=False),
                            )
                        )

            # temporal check
            if temporal_columns:
                # check the data types of the data frame columns
                incorrect_data_type_columns = [
                    item
                    for item in temporal_columns
                    if item in data_loaded_sheets[sheet].data.columns
                    and not data_loaded_sheets[sheet].data.schema[item].is_temporal()
                ]

                if incorrect_data_type_columns:
                    # if there are dataframe columns with the incorrect data type
                    # then check the column values

                    # pivot the table to make the process easier
                    check_df = (
                        data_loaded_sheets[sheet]
                        .data.select(
                            [check_sheet_id_column.data_column_name] + incorrect_data_type_columns
                        )
                        .unpivot(
                            index=check_sheet_id_column.data_column_name,
                            variable_name="question",
                            value_name="value",
                        )
                    )
                    # find invalid values
                    # if the value cant be converted it will return null.
                    # this is used as a filter on the dataframe
                    # if the column is numeric (likely utc) then this will
                    # currently also throw an error

                    # This was split into two expressions as to_datetime threw an error for numeric
                    # values:
                    # incorrect_values_df = check_df.filter(pl.col("value").is_not_null()).filter(
                    #     (check_df.schema["value"].is_numeric())
                    #     | (
                    #         pl.col("value")
                    #         .str.to_datetime(strict=False, ambiguous='null')
                    #         # .cast(pl.Datetime, strict=False)
                    #         .is_null()
                    #     )

                    # get numeric values first
                    incorrect_values_df = check_df.filter(pl.col("value").is_not_null()).filter(
                        check_df.schema["value"].is_numeric()
                        | pl.col("value").cast(pl.Float64, strict=False).is_not_null()
                    )

                    # filter numeric values out then try converting to datetime to
                    # get non datetime values
                    incorrect_values_non_numeric_df = check_df.filter(
                        pl.col("value").is_not_null()
                        & (not check_df.schema["value"].is_numeric())
                        & pl.col("value").cast(pl.Float64, strict=False).is_null()
                    ).filter(
                        pl.col("value")
                        .cast(pl.String)
                        .str.to_datetime(strict=False, ambiguous="null")
                        .is_null()
                    )

                    incorrect_values_df = pl.concat(
                        [incorrect_values_df, incorrect_values_non_numeric_df]
                    )

                    if incorrect_values_df.height > 0:
                        date_issue_message = self._(
                            "column_data_type_validator.temporal_check.issue"
                        )

                        incorrect_values_df = incorrect_values_df.with_columns(
                            pl.lit(sheet).alias("sheet"),
                            pl.lit(date_issue_message).alias("issue"),
                        )
                        results.append(
                            ValidationResult(
                                rule=self.name,
                                message=self._(
                                    "column_data_type_validator.temporal_check",
                                    count=incorrect_values_df.height,
                                    sheet=sheet,
                                ),
                                severity=SeverityLevel.ERROR,
                                sheet_name=sheet,
                                details=incorrect_values_df.to_dict(as_series=False),
                            )
                        )

        return results
