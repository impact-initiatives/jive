from typing import override

import polars as pl

from ...common.list_matching import filter_list
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


class CleaningLogToCleanCheck(BaseValidator):
    """This process validates the data in the cleaning log

    After making sure that the required sheets and columns have been loaded and matched
    the process validates that all the items in a cleaning log are reflected in
      the clean data.

    The output includes:
    - items in cleaning log that have multiple updates for the same question
    - questions in cleaning log that are not present in clean_data
    - items where there is a difference between cleaning_log and clean_data values

    """

    def __init__(
        self,
        schema: BaseDatasetSchema,
        clean_data_sheet: str = "clean_data",
        cleaning_log_sheet: str = "cleaning_log",
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
        self.cleaning_log_sheet: str = cleaning_log_sheet
        self.cleaning_log_new_value_column: str = cleaning_log_new_value_column
        self.cleaning_log_old_value_column: str = cleaning_log_old_value_column
        self.cleaning_log_question_column: str = cleaning_log_question_column
        self.cleaning_log_change_type_column: str = cleaning_log_change_type_column
        # the ProcessValueMap that contains the list of possible values needed in
        # cleaning_log_change_type_column
        self.process_value_map_name: str = "cleaning_log_validation"
        self.exclude_id_values: list[str] = (
            exclude_id_values if exclude_id_values is not None else ["all"]
        )

    @property
    @override
    def name(self) -> str:
        return "CleaningLogToCleanCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """This process validates the data in the cleaning log

        After making sure that the required sheets and columns have been loaded
        and matched the process validates that all the items in a cleaning log
        are reflected in the clean data.


        The output includes:
        - items in cleaning log that have multiple updates for the same question
        - questions in cleaning log that are not present in clean_data
        - items where there is a difference between cleaning_log and clean_data values

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        # PRE-VALIDATION - check sheets, columns etc all exist

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.clean_data_sheet, self.cleaning_log_sheet],
            rule=self.name,
            check_data=False,
        )

        if result is not None:
            results.append(result)
            return results

        result, schema_loaded_sheets = get_schema_loaded_sheets(
            schema=self.schema, sheet_names=[self.cleaning_log_sheet], rule=self.name
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
        if clean_data_id_columns is None or cleaning_log_id_columns is None:
            return results
        assert cleaning_log_id_columns is not None
        assert clean_data_id_columns is not None

        result, data_loaded_columns = get_data_loaded_columns(
            data={
                self.cleaning_log_new_value_column: data_loaded_sheets[self.cleaning_log_sheet],
                self.cleaning_log_old_value_column: data_loaded_sheets[self.cleaning_log_sheet],
                self.cleaning_log_question_column: data_loaded_sheets[self.cleaning_log_sheet],
                self.cleaning_log_change_type_column: data_loaded_sheets[self.cleaning_log_sheet],
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
            # this should already have been validated when checking mandatory columns
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
                pl.col(data_loaded_columns[self.cleaning_log_change_type_column].data_column_name)
                .str.to_lowercase()
                .is_in(schema_change_type_values.values)
            )
            .filter(
                (clean_log_id_columns_filter.is_not_null()) & (clean_log_id_columns_filter != "")
            )
            .filter(
                pl.col(cleaning_log_id_columns.data_column_name)
                .cast(pl.String)
                .str.to_lowercase()
                .is_in(self.exclude_id_values)
                .not_()
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

        if modified_rows_df.height == 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "cleaning_log_to_clean_validator.no_changes",
                        values=", ".join(f"'{item}'" for item in schema_change_type_values.values),
                        sheet=self.cleaning_log_sheet,
                        column=data_loaded_columns[
                            self.cleaning_log_change_type_column
                        ].data_column_name,
                    ),
                    sheet_name=self.cleaning_log_sheet,
                    severity=SeverityLevel.ERROR,
                )
            )
            return results

        # Compares the cleaning log to clean_data

        # records where the same question was updated more than once for the same id
        multiple_change_mask = modified_rows_df.select(
            cleaning_log_id_columns.data_column_name,
            data_loaded_columns[self.cleaning_log_question_column].data_column_name,
        ).is_duplicated()

        multiple_change_issue_message = self._(
            "cleaning_log_to_clean_validator.multiple_changes.issue",
            question_column=self.cleaning_log_question_column,
            id_column=cleaning_log_id_columns.data_column_name,
        )
        multiple_change_df = (
            modified_rows_df.filter(multiple_change_mask)
            .sort(cleaning_log_id_columns.data_column_name)
            .select(
                pl.col(cleaning_log_id_columns.data_column_name).alias("uuid"),
                data_loaded_columns[self.cleaning_log_question_column].data_column_name,
            )
            .with_columns(
                [
                    pl.lit(cleaning_log_id_columns.data_column_name).alias("uuid_column_name"),
                    pl.lit(multiple_change_issue_message).alias("issue"),
                    pl.lit(self.cleaning_log_sheet).alias("cleaning_log sheet"),
                    pl.lit(self.clean_data_sheet).alias("clean_data sheet"),
                ]
            )
        )

        if multiple_change_df.height > 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "cleaning_log_to_clean_validator.multiple_changes",
                        count=multiple_change_df.select(
                            [
                                pl.col("uuid"),
                                pl.col(
                                    data_loaded_columns[
                                        self.cleaning_log_question_column
                                    ].data_column_name
                                ),
                            ]
                        ).n_unique(),
                    ),
                    severity=SeverityLevel.WARNING,
                    sheet_name=self.cleaning_log_sheet,
                    details=multiple_change_df.to_dict(as_series=False),
                )
            )

        # scan cleaning log for old value = new value
        same_value_issue_message = self._(
            "cleaning_log_to_clean_validator.same_value.issue",
            new_value_column=data_loaded_columns[
                self.cleaning_log_new_value_column
            ].data_column_name,
            old_value_column=data_loaded_columns[
                self.cleaning_log_old_value_column
            ].data_column_name,
        )
        same_value_df = (
            modified_rows_df.filter(
                pl.col(
                    data_loaded_columns[self.cleaning_log_new_value_column].data_column_name
                ).cast(pl.Utf8)
                == pl.col(
                    data_loaded_columns[self.cleaning_log_old_value_column].data_column_name
                ).cast(pl.Utf8)
            )
            .select(
                pl.col(cleaning_log_id_columns.data_column_name).alias("uuid"),
                pl.lit(cleaning_log_id_columns.data_column_name).alias("uuid_column_name"),
                data_loaded_columns[self.cleaning_log_new_value_column].data_column_name,
                data_loaded_columns[self.cleaning_log_old_value_column].data_column_name,
                data_loaded_columns[self.cleaning_log_change_type_column].data_column_name,
            )
            .with_columns(
                [
                    pl.lit(same_value_issue_message).alias("issue"),
                    pl.lit(self.cleaning_log_sheet).alias("cleaning_log sheet"),
                ]
            )
        )
        if same_value_df.height > 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "cleaning_log_to_clean_validator.same_value",
                        count=same_value_df.height,
                        old_value_column=data_loaded_columns[
                            self.cleaning_log_old_value_column
                        ].data_column_name,
                        new_value_column=data_loaded_columns[
                            self.cleaning_log_new_value_column
                        ].data_column_name,
                    ),
                    severity=SeverityLevel.WARNING,
                    sheet_name=self.cleaning_log_sheet,
                    details=same_value_df.to_dict(as_series=False),
                )
            )

        # remove records with multiple chages as there is no way to determine
        #  which should be the most recent
        # also remove other columns as they are no longer necessary
        unique_modified_rows_df = (
            modified_rows_df.filter(~multiple_change_mask)
            .sort(cleaning_log_id_columns.data_column_name)
            .select(
                [
                    cleaning_log_id_columns.data_column_name,
                    data_loaded_columns[self.cleaning_log_new_value_column].data_column_name,
                    data_loaded_columns[self.cleaning_log_question_column].data_column_name,
                ]
            )
        )

        if unique_modified_rows_df.height < 1:
            return results
        # get a list of questions that had values changed
        # remove the id column in the rare case its in the list of quesitons
        questions = filter_list(
            unique_modified_rows_df.select(
                data_loaded_columns[self.cleaning_log_question_column].data_column_name
            )
            .unique()
            .to_series()
            .str.to_lowercase()
            .to_list(),
            [clean_data_id_columns.data_column_name],
        )

        # questions in cleaning log not iin clean data
        missing_questions_issue_message = self._(
            "cleaning_log_to_clean_validator.missing_questions.issue",
            column=data_loaded_columns[self.cleaning_log_question_column].data_column_name,
            sheet=self.clean_data_sheet,
        )

        missing_quesitons = filter_list(
            questions, data_loaded_sheets[self.clean_data_sheet].data.columns
        )
        if missing_quesitons:
            missing_quesitons_df = pl.DataFrame(
                {
                    data_loaded_columns[
                        self.cleaning_log_question_column
                    ].data_column_name: missing_quesitons
                }
            ).with_columns(
                [
                    pl.lit(missing_questions_issue_message).alias("issue"),
                    pl.lit(self.cleaning_log_sheet).alias("cleaning_log sheet"),
                    pl.lit(self.clean_data_sheet).alias("clean_data sheet"),
                ]
            )
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "cleaning_log_to_clean_validator.missing_questions",
                        cleaning_log_sheet=data_loaded_sheets[
                            self.cleaning_log_sheet
                        ].data_sheet_name,
                        clean_data_sheet=data_loaded_sheets[self.clean_data_sheet].data_sheet_name,
                    ),
                    severity=SeverityLevel.WARNING,
                    sheet_name=self.cleaning_log_sheet,
                    details=missing_quesitons_df.to_dict(as_series=False),
                )
            )
            questions = filter_list(questions, missing_quesitons)
            if len(questions) < 1:
                # if no valid questions left to check
                return results

        # add column to specifiy an update. this helps to specify which
        # questions were updated later after the pivot as the pivot will
        # add a column for each question even if that question was not updated
        # for a particular uuid.
        # The result of this will be that question columns
        # that actually had an update in cleaning log will have 'true' for that question
        # while all other other questions will be null
        # fill null with '' to make comparison easier later
        unique_modified_rows_df = unique_modified_rows_df.with_columns(
            pl.lit(True).alias("is_update")
        ).with_columns(
            pl.col(data_loaded_columns[self.cleaning_log_new_value_column].data_column_name)
        )  # .fill_null(''))

        # pivot the table for use later. lower the questions/column names.
        unique_modified_rows_df = unique_modified_rows_df.pivot(
            on=data_loaded_columns[self.cleaning_log_question_column].data_column_name,
            index=cleaning_log_id_columns.data_column_name,
            values=[
                data_loaded_columns[self.cleaning_log_new_value_column].data_column_name,
                "is_update",
            ],
        ).rename(str.lower)
        # rename for later
        # the question prefix comes from the column name in the pivot operation
        unique_modified_rows_df = unique_modified_rows_df.rename(
            {
                f"{data_loaded_columns[self.cleaning_log_new_value_column].data_column_name}_{
                    q
                }": f"{q}_val"
                for q in questions
            }
        ).rename({f"is_update_{q}": f"{q}_has_update" for q in questions})

        # filter the clean_data sheet to only have records that are in the cleaning log
        # and only select the questions that were present in the cleaning log
        # fill empty values to '' to make comparison easier later
        clean_data_filtered_df = (
            data_loaded_sheets[self.clean_data_sheet]
            .data.select([clean_data_id_columns.data_column_name] + questions)
            .filter(
                pl.col(clean_data_id_columns.data_column_name).is_in(
                    unique_modified_rows_df[cleaning_log_id_columns.data_column_name].implode()
                )
            )
        )
        # .fill_null('')
        # join dataframes so columns can be matched below
        joined_df = unique_modified_rows_df.join(
            other=clean_data_filtered_df,
            left_on=cleaning_log_id_columns.data_column_name,
            right_on=clean_data_id_columns.data_column_name,
            how="left",
        )

        # build expressions to check for differences in the two dataframes
        difference_expressions = []
        for question in questions:
            column_has_update = f"{question}_has_update"
            # Check if the new value exists AND is different from the old value

            difference_expression = (
                create_column_difference_expression(
                    question,
                    f"{question}_val",
                    joined_df.schema[question],
                    joined_df.schema[f"{question}_val"],
                )
            ).alias(f"is_{question}_changed")

            difference_expression = (
                pl.when(pl.col(column_has_update).is_not_null())
                .then(difference_expression)
                .otherwise(pl.col(column_has_update).is_not_null())
            )

            difference_expressions.append(difference_expression)

        # check for changes
        has_any_change = pl.any_horizontal(
            [pl.col(f"is_{question}_changed") for question in questions]
        )
        # Add the difference flags to the dataframe
        changes_only = joined_df.with_columns(difference_expressions).filter(has_any_change)

        # record the changes
        # The unpivot process transforms the data from a wide format into a long format.
        #  By running this separately on the new values, old values, and change flags,
        #  we create three aligned vertical lists that can be joined together using
        # the uuid and question name. This allows us to filter for changes and compare
        # old vs. new values in a single operation.
        if not changes_only.is_empty():
            # unpivot values (clean_data)
            new_values_df = changes_only.unpivot(
                index=[cleaning_log_id_columns.data_column_name],
                on=questions,
                variable_name=data_loaded_columns[
                    self.cleaning_log_question_column
                ].data_column_name,
                value_name=f"{self.clean_data_sheet}_value",
            )

            #    unpivot values (cleaning log)
            # need to rename so question names match
            original_values_df = (
                changes_only.select(
                    [cleaning_log_id_columns.data_column_name] + [f"{q}_val" for q in questions]
                )
                .rename({f"{q}_val": q for q in questions})
                .unpivot(
                    index=[cleaning_log_id_columns.data_column_name],
                    on=questions,  # Now unpivoting the renamed columns
                    variable_name=data_loaded_columns[
                        self.cleaning_log_question_column
                    ].data_column_name,
                    value_name=f"{self.cleaning_log_sheet}_value",
                )
            )

            # unpivot flags. Extract question name from flag column name
            flags_long_df = changes_only.unpivot(
                index=[cleaning_log_id_columns.data_column_name],
                on=[f"is_{q}_changed" for q in questions],
                variable_name="flag_column_name",
                value_name="is_changed",
            ).with_columns(
                pl.col("flag_column_name")
                .str.replace("^is_", "", literal=False)
                .str.replace("_changed$", "", literal=False)
                .alias(data_loaded_columns[self.cleaning_log_question_column].data_column_name)
            )

            # join all together.  Filter the changed rows
            merged_df = (
                new_values_df.join(
                    original_values_df,
                    on=[
                        cleaning_log_id_columns.data_column_name,
                        data_loaded_columns[self.cleaning_log_question_column].data_column_name,
                    ],
                    how="inner",
                )
                .join(
                    flags_long_df,
                    on=[
                        cleaning_log_id_columns.data_column_name,
                        data_loaded_columns[self.cleaning_log_question_column].data_column_name,
                    ],
                    how="inner",
                )
                .filter(pl.col("is_changed"))
            )

            # select the columns because they are all present in the merged DF
            differences_issue_message = self._(
                "cleaning_log_to_clean_validator.differences.issue",
                sheet=self.clean_data_sheet,
            )
            difference_df = merged_df.select(
                [
                    pl.col(cleaning_log_id_columns.data_column_name).alias("uuid"),
                    pl.col(data_loaded_columns[self.cleaning_log_question_column].data_column_name),
                    pl.col(f"{self.cleaning_log_sheet}_value").alias("cleaning_log_value"),
                    pl.col(f"{self.clean_data_sheet}_value").alias("clean_data_value"),
                ]
            ).with_columns(
                [
                    pl.lit(cleaning_log_id_columns.data_column_name).alias("uuid_column_name"),
                    pl.lit(differences_issue_message).alias("issue"),
                    pl.lit(self.cleaning_log_sheet).alias("cleaning_log sheet"),
                    pl.lit(self.clean_data_sheet).alias("clean_data sheet"),
                ]
            )

            # if there are differences found log them
            if difference_df.height > 0:
                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            "cleaning_log_to_clean_validator.differences",
                            count=difference_df.height,
                            cleaning_log_sheet=self.cleaning_log_sheet,
                            clean_data_sheet=self.clean_data_sheet,
                        ),
                        severity=SeverityLevel.ERROR,
                        sheet_name=self.cleaning_log_sheet,
                        details=difference_df.to_dict(as_series=False),
                    )
                )

        return results
