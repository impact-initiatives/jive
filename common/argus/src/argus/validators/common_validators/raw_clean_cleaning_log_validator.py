from typing import override

import polars as pl

from ...common.list_matching import filter_list, match_list
from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_columns,
    get_data_loaded_sheets,
    get_id_linking_columns,
)
from ..helpers.expression_builder import create_column_difference_expression
from ..helpers.schema_helpers import get_schema_loaded_sheets, get_schema_process_value


class RawToCleanToLogCheck(BaseValidator):
    """This process compares the differences between the clean and raw data sheets
    and then checks that all these differences are reflected in the cleaning log
    if provided

    The output includes:
    - items where there is a difference between raw_data/clean_data and the cleaning log
    - if no cleaning log is provided then an error is returned if there are differences
        between raw and clean

    """

    def __init__(
        self,
        schema: BaseDatasetSchema,
        clean_data_sheet: str = "clean_data",
        raw_data_sheet: str = "raw_data",
        cleaning_log_sheet: str | None = "cleaning_log",
        cleaning_log_new_value_column: str = "new_value",
        cleaning_log_old_value_column: str = "old_value",
        cleaning_log_question_column: str = "variable",
        cleaning_log_change_type_column: str = "change_type",
        exclude_id_values: list[str] | None = None,
    ) -> None:
        """Validates that the items in a cleaning log are reflected in the clean data

        Args:
            schema (BaseDatasetSchema): dataset schema for the dataset
            clean_data_sheet (str, optional): name of the clean data sheet.
                Defaults to 'clean_data'.
            raw_data_sheet (str, optional): name of the raw data sheet.
                Defaults to 'raw_data'.
            cleaning_log_sheet (str, optional): name of the cleaning log sheet.
                Defaults to 'cleaning_log'.
            cleaning_log_new_value_column (str, optional): name of the cleaning log
                new value column. Defaults to 'new_value'.
            cleaning_log_old_value_column (str, optional): name of the cleaning log
                old value column. Defaults to 'old_value'.
            cleaning_log_question_column (str, optional): name of the cleaning log
                quesitons column. Defaults to 'question'.
            cleaning_log_change_type_column (str, optional): name of the cleaning log
                change_type column. Defaults to 'change_type'
            exclude_id_values (list[str] | None): used to filter out questions from
                this check. ie, when uuid == 'all'
        """
        self.schema: BaseDatasetSchema = schema
        self.clean_data_sheet: str = clean_data_sheet
        self.raw_data_sheet: str = raw_data_sheet
        self.cleaning_log_sheet: str | None = cleaning_log_sheet
        self.cleaning_log_new_value_column: str = cleaning_log_new_value_column
        self.cleaning_log_old_value_column: str = cleaning_log_old_value_column
        self.cleaning_log_question_column: str = cleaning_log_question_column
        self.cleaning_log_change_type_column: str = cleaning_log_change_type_column
        # the ProcessValueMap that contains the list of possible values needed in
        #  cleaning_log_change_type_column
        self.process_value_map_name: str = "cleaning_log_validation"
        self.exclude_id_values: list[str] = (
            exclude_id_values if exclude_id_values is not None else ["all"]
        )

    @property
    @override
    def name(self) -> str:
        return "RawToCleanToLogCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """This process compares the differences between the clean and raw data sheets
        and then checks that all these differences are reflected in the cleaning log if
        provided

        The output includes:
        - items where there is a difference between raw_data/clean_data and the
            cleaning log
        - if no cleaning log is provided then an error is returned if there are
            differences between raw and clean

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []
        all_column_variables: list[str] = []

        # PRE-VALIDATION - check sheets, columns etc all exist

        sheet_names = [self.clean_data_sheet, self.raw_data_sheet]
        if self.cleaning_log_sheet is not None:
            sheet_names.append(self.cleaning_log_sheet)

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data, sheet_names=sheet_names, rule=self.name, check_data=False
        )

        if result is not None:
            results.append(result)
            return results

        result, clean_data_id_columns, raw_data_id_columns = get_id_linking_columns(
            schema=self.schema,
            data_loaded_sheets=data_loaded_sheets,
            source_sheet=self.clean_data_sheet,
            target_sheet=self.raw_data_sheet,
            rule=self.name,
        )
        results.extend(result)
        if raw_data_id_columns is None or clean_data_id_columns is None:
            return results
        assert raw_data_id_columns is not None
        assert clean_data_id_columns is not None

        if self.cleaning_log_sheet is not None:
            result, schema_loaded_sheets = get_schema_loaded_sheets(
                schema=self.schema,
                sheet_names=[self.cleaning_log_sheet],
                rule=self.name,
            )
            if result is not None:
                results.append(result)
                return results

            result, cleaning_log_id_columns, clean_data_id_columns = get_id_linking_columns(
                schema=self.schema,
                data_loaded_sheets=data_loaded_sheets,
                source_sheet=self.cleaning_log_sheet,
                target_sheet=self.clean_data_sheet,
                rule=self.name,
                exclude_id_values=self.exclude_id_values,
            )
            results.extend(result)
            if cleaning_log_id_columns is None or clean_data_id_columns is None:
                return results
            assert clean_data_id_columns is not None
            assert cleaning_log_id_columns is not None

            result, data_loaded_columns = get_data_loaded_columns(
                data={
                    self.cleaning_log_new_value_column: data_loaded_sheets[self.cleaning_log_sheet],
                    self.cleaning_log_old_value_column: data_loaded_sheets[self.cleaning_log_sheet],
                    self.cleaning_log_question_column: data_loaded_sheets[self.cleaning_log_sheet],
                    self.cleaning_log_change_type_column: data_loaded_sheets[
                        self.cleaning_log_sheet
                    ],
                },
                rule=self.name,
            )

            if result is not None:
                results.append(result)
                return results

            schema_change_type_column = schema_loaded_sheets[self.cleaning_log_sheet].get_column(
                self.cleaning_log_change_type_column
            )
            if schema_change_type_column is None:
                # this should already have been validated when checking
                # mandatory columns
                return results

            result, schema_change_type_values = get_schema_process_value(
                self.process_value_map_name,
                self.cleaning_log_sheet,
                schema_change_type_column,
                self.name,
            )
            if result is not None:
                results.append(result)
                return results

            assert schema_change_type_values is not None

            # TRANSFORMATION: transforms data in preparation for comparison
            # dataframe of actual changes made
            clean_log_id_columns_filter = (
                pl.col(cleaning_log_id_columns.data_column_name).cast(pl.Utf8).str.strip_chars(" ")
            )

            modified_rows_df = (
                data_loaded_sheets[self.cleaning_log_sheet]
                .data.filter(
                    pl.col(
                        data_loaded_columns[self.cleaning_log_change_type_column].data_column_name
                    )
                    .str.to_lowercase()
                    .is_in(schema_change_type_values.values)
                )
                .filter(
                    (clean_log_id_columns_filter.is_not_null())
                    & (clean_log_id_columns_filter != "")
                )
                .select(
                    [
                        cleaning_log_id_columns.data_column_name,
                        data_loaded_columns[self.cleaning_log_new_value_column].data_column_name,
                        data_loaded_columns[self.cleaning_log_old_value_column].data_column_name,
                        data_loaded_columns[self.cleaning_log_change_type_column].data_column_name,
                        data_loaded_columns[self.cleaning_log_question_column].data_column_name,
                    ]
                )
            )

            # variables/questions in cleaning log where uuid == "all"
            all_column_variables = (
                data_loaded_sheets[self.cleaning_log_sheet]
                .data.filter(
                    pl.col(cleaning_log_id_columns.data_column_name)
                    .cast(pl.String)
                    .str.to_lowercase()
                    .is_in(self.exclude_id_values)
                )
                .select(
                    pl.col(data_loaded_columns[self.cleaning_log_question_column].data_column_name)
                )
                .unique()
                .to_series()
                .to_list()
            )

            if all_column_variables:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            "cleaning_log.all_values",
                            count=len(all_column_variables),
                            sheet=self.cleaning_log_sheet,
                            columns=", ".join(all_column_variables),
                            uuid_column=cleaning_log_id_columns.data_column_name,
                            question_column=data_loaded_columns[
                                self.cleaning_log_question_column
                            ].data_column_name,
                        ),
                        severity=SeverityLevel.INFO,
                        sheet_name=self.cleaning_log_sheet,
                    )
                )

        # Gets the difference between raw and clean sheets and compares
        # this to the cleaning log
        # get columns that are in both clean and raw sheets
        # then filter the sheets
        clean_data_columns = filter_list(
            match_list(
                data_loaded_sheets[self.clean_data_sheet].data.columns,
                data_loaded_sheets[self.raw_data_sheet].data.columns,
            ),
            [clean_data_id_columns.data_column_name],
        )

        if all_column_variables:
            clean_data_columns = filter_list(clean_data_columns, all_column_variables)

        difference_parts: list[pl.DataFrame] = []

        # use chunking to reduce memory usage
        for start in range(0, len(clean_data_columns), settings.COLUMN_CHUNK_SIZE):
            clean_data_columns_chunked = clean_data_columns[
                start : start + settings.COLUMN_CHUNK_SIZE
            ]

            clean_data_filtered_chunked_df = data_loaded_sheets[self.clean_data_sheet].data.select(
                [clean_data_id_columns.data_column_name] + clean_data_columns_chunked
            )
            raw_data_filtered_chunked_df = (
                data_loaded_sheets[self.raw_data_sheet]
                .data.select([raw_data_id_columns.data_column_name] + clean_data_columns_chunked)
                .rename({f"{q}": f"{q}_original_value" for q in clean_data_columns_chunked})
            )

            # join the dataframes so that only ids in both are compared
            joined_chunked_df = raw_data_filtered_chunked_df.join(
                other=clean_data_filtered_chunked_df,
                left_on=raw_data_id_columns.data_column_name,
                right_on=clean_data_id_columns.data_column_name,
                how="inner",
            )

            # build expressions to compare the columns of both dataframes
            chunk_difference_expressions: list[pl.Expr] = [
                create_column_difference_expression(
                    question,
                    f"{question}_original_value",
                    joined_chunked_df.schema[question],
                    joined_chunked_df.schema[f"{question}_original_value"],
                ).alias(f"is_{question}_changed")
                for question in clean_data_columns_chunked
            ]

            # add the difference flags to the dataframe and checl for changes
            has_any_change = pl.any_horizontal(
                [pl.col(f"is_{question}_changed") for question in clean_data_columns_chunked]
            )
            changes_only_chunked_df = joined_chunked_df.with_columns(
                chunk_difference_expressions
            ).filter(has_any_change)

            # The unpivot process transforms the data from a wide format into a long format.
            #  By running this separately on the new values, old values, and change flags,
            #  we create three aligned vertical lists that can be joined together using
            #  the uuid and question name. This allows us to filter for changes and compare
            # old vs. new values in a single operation.

            if not changes_only_chunked_df.is_empty():
                # the index id has to be the column that was the 'left_on' value when
                # creating joined_df

                # unpivot new values (clean data)
                new_values_chunked_df = changes_only_chunked_df.unpivot(
                    index=[raw_data_id_columns.data_column_name],
                    on=clean_data_columns_chunked,
                    variable_name=self.cleaning_log_question_column,
                    value_name=self.cleaning_log_new_value_column,
                )

                # unpivot original values (raw data)
                # need to rename so question names match
                original_values_chunked_df = (
                    changes_only_chunked_df.select(
                        [raw_data_id_columns.data_column_name]
                        + [f"{q}_original_value" for q in clean_data_columns_chunked]
                    )
                    .rename({f"{q}_original_value": q for q in clean_data_columns_chunked})
                    .unpivot(
                        index=[raw_data_id_columns.data_column_name],
                        on=clean_data_columns_chunked,  # Now unpivoting the renamed columns
                        variable_name=self.cleaning_log_question_column,
                        value_name=self.cleaning_log_old_value_column,
                    )
                )

                # unpivot flags. Extract question name from flag column name
                flags_long_chunked_df = changes_only_chunked_df.unpivot(
                    index=[raw_data_id_columns.data_column_name],
                    on=[f"is_{q}_changed" for q in clean_data_columns_chunked],
                    variable_name="flag_column_name",
                    value_name="is_changed",
                ).with_columns(
                    pl.col("flag_column_name")
                    .str.replace("^is_", "", literal=False)
                    .str.replace("_changed$", "", literal=False)
                    .alias(self.cleaning_log_question_column)
                )

                # join all together. Filter the changed rows
                merged_chunked_df = (
                    new_values_chunked_df.join(
                        original_values_chunked_df,
                        on=[
                            raw_data_id_columns.data_column_name,
                            self.cleaning_log_question_column,
                        ],
                        how="inner",
                    )
                    .join(
                        flags_long_chunked_df,
                        on=[
                            raw_data_id_columns.data_column_name,
                            self.cleaning_log_question_column,
                        ],
                        how="inner",
                    )
                    .filter(pl.col("is_changed"))
                )

                difference_parts.append(
                    merged_chunked_df.select(
                        [
                            pl.col(raw_data_id_columns.data_column_name).alias("uuid"),
                            pl.col(self.cleaning_log_question_column),
                            pl.col(self.cleaning_log_old_value_column),
                            pl.col(self.cleaning_log_new_value_column),
                        ]
                    )
                )
                del (
                    joined_chunked_df,
                    changes_only_chunked_df,
                    new_values_chunked_df,
                    original_values_chunked_df,
                    flags_long_chunked_df,
                )

        if difference_parts:
            # select the columns because they are all present in the merged DF
            difference_raw_to_clean_df = pl.concat(difference_parts, how="vertical").with_columns(
                pl.lit(raw_data_id_columns.data_column_name).alias("uuid_column_name")
            )

            # difference between above and cleaning log
            # This does not check the actual values. It only checks that
            # there is a cleaning log record when there should be one for a uuid and question
            # if the actual values are incorrect that should be picked up
            # by CleaningLogToCleanCheck
            if self.cleaning_log_sheet is not None:
                difference_issue_message = self._(
                    "raw_clean_cleaning_log_validator.cleaning_log_diff.issue",
                    sheet=self.cleaning_log_sheet,
                )
                difference_df = difference_raw_to_clean_df.join(
                    other=modified_rows_df,  # pyright: ignore[reportPossiblyUnboundVariable]
                    how="anti",
                    left_on=["uuid", self.cleaning_log_question_column],
                    right_on=[
                        cleaning_log_id_columns.data_column_name,  # pyright: ignore[reportPossiblyUnboundVariable]
                        data_loaded_columns[self.cleaning_log_question_column].data_column_name,  # pyright: ignore[reportPossiblyUnboundVariable]
                    ],
                ).with_columns(
                    [
                        pl.lit(difference_issue_message).alias("issue"),
                        pl.lit(self.cleaning_log_sheet).alias("cleaning_log sheet"),
                        pl.lit(self.clean_data_sheet).alias("clean_data sheet"),
                        pl.lit(self.raw_data_sheet).alias("raw_data sheet"),
                    ]
                )

                if difference_df.height > 0:
                    results.append(
                        ValidationResult(
                            rule=self.name,
                            message=self._(
                                "raw_clean_cleaning_log_validator.cleaning_log_diff",
                                count=difference_df.height,
                                clean_sheet=self.clean_data_sheet,
                                log_sheet=self.cleaning_log_sheet,
                            ),
                            severity=SeverityLevel.ERROR,
                            sheet_name=self.cleaning_log_sheet,
                            details=difference_df.to_dict(as_series=False),
                        )
                    )
            else:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            "raw_clean_cleaning_log_validator.diff_no_cleaning_log",
                            count=difference_raw_to_clean_df.height,
                            clean_sheet=self.clean_data_sheet,
                            raw_sheet=self.raw_data_sheet,
                        ),
                        severity=SeverityLevel.ERROR,
                        sheet_name=self.cleaning_log_sheet,
                        details=difference_raw_to_clean_df.with_columns(
                            [
                                pl.lit(f"change not reflected in {self.cleaning_log_sheet}").alias(
                                    "issue"
                                ),
                                pl.lit(self.clean_data_sheet).alias("clean_data sheet"),
                                pl.lit(self.raw_data_sheet).alias("raw_data sheet"),
                            ]
                        ).to_dict(as_series=False),
                    )
                )

        return results
