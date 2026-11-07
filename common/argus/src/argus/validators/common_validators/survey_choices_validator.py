from typing import override

import polars as pl

from ...common.list_matching import filter_loaded_sheets, match_list
from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_columns,
    get_data_loaded_sheets,
    get_data_sheet_ids,
)
from ..helpers.expression_builder import normalise_list


class SurveyChoicesCheck(BaseValidator):
    """Checks that clean_data values are valid when they come from
    kobo select_one or select_multiple quesitons.
    """

    def __init__(
        self,
        schema: BaseDatasetSchema,
        survey_sheet: str = settings.SURVEY_SHEET_NAME,
        survey_type_column: str = "type",
        survey_name_column: str = "name",
        choices_sheet: str = settings.CHOICES_SHEET_NAME,
        choices_name_column: str = "name",
        choices_list_name_column: str = "list_name",
        check_sheets: list[str] | None = None,
        select_multiple_value_separator: str = " ",
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
            choices_sheet (str, optional): name of the kobo choices sheet in excel.
                Defaults to 'choices'.
            choices_name_column (str, optional): name of the name column in the
                kobo choices sheet. Defaults to 'name'.
            choices_list_name_column (str, optional): name of the list_name column in
                the kobo choices sheet. Defaults to 'list_name'.
            check_sheets (List, optional): schema sheet names to check.
                Defaults to ['clean_data'].
            select_multiple_value_separator (str, optional): select_multiple value
                separator. Defaults to ' '.
        """
        self.schema: BaseDatasetSchema = schema
        self.survey_sheet: str = survey_sheet
        self.check_sheets: list[str] = check_sheets if check_sheets is not None else ["clean_data"]
        self.survey_type_column: str = survey_type_column
        self.survey_name_column: str = survey_name_column
        self.choices_sheet: str = choices_sheet
        self.choices_name_column: str = choices_name_column
        self.choices_list_name_column: str = choices_list_name_column
        # select_multiple values are stored as one value separated by delimiter
        self.select_multiple_value_separator: str = select_multiple_value_separator

    @property
    @override
    def name(self) -> str:
        return "SurveyChoicesCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks that clean_data values are valid when they come from
        kobo select_one or select_multiple questions.

            This process:
                -performs prevalidation to make sure expected sheets, columns etc
                    are present
                - performs some transformations on the kobo questions and choices
                - for each check_sheet, gets the relevant questions, builds an
                    expression to check for valid values and records invalid values.
                - the process to build an expression is slightly different for
                    select_one and select_multiple as they have to handle
                    spaces in values differntly. see comments in the code for details.

            Args:
                data (ExcelLoaderData): excel data to validate

            Returns:
                List[ValidationResult]: list of validation errors
        """

        # add issue text
        def _get_difference(
            difference_expressions: list[pl.Expr], question_suffix: str, questions: list[str]
        ) -> pl.DataFrame | None:
            """Computes the actual differences between the choice values and the data values
            using built expressions.

            Args:
                difference_expressions (list[pl.Expr]): Built polars expression that finds value
                    differences.
                question_suffix (str): The suffix used to tag the expression columns
                questions (list[str]): list of questions that are part of the expressions

            Returns:
                Dataframe | None: Data with details of differences found, otherwise None
            """
            # Get the invalid values
            comparison_df = data_loaded_sheets[sheet].data.with_columns(difference_expressions)
            has_any_change = pl.any_horizontal(
                [pl.col(f"{question}_{question_suffix}") for question in questions]
            )
            changes_only = comparison_df.filter(has_any_change)

            # report the invalid values if any
            # transform data from a wide format to a long format and join to flags.
            # this allows for filtering invalid values in a single operation
            if not changes_only.is_empty():
                values_df = changes_only.unpivot(
                    index=[check_sheet_id_column.data_column_name],
                    on=questions,
                    variable_name="question",
                    value_name="value",
                )

                # unpivot flags. Extract question name from flag column name
                flags_df = changes_only.unpivot(
                    index=[check_sheet_id_column.data_column_name],
                    on=[f"{question}_{question_suffix}" for question in questions],
                    variable_name="flag_column_name",
                    value_name="is_changed",
                ).with_columns(
                    pl.col("flag_column_name")
                    .str.replace("^is_", "", literal=False)
                    .str.replace(f"_{question_suffix}$", "", literal=False)
                    .alias("question")
                )

                merged_df = values_df.join(
                    flags_df,
                    on=[check_sheet_id_column.data_column_name, "question"],
                    how="inner",
                ).filter(pl.col("is_changed"))

                difference_df = merged_df.select(
                    [
                        pl.col(check_sheet_id_column.data_column_name)
                        .cast(pl.String)
                        .alias("uuid"),
                        pl.lit(sheet).alias("sheet"),
                        pl.col("question"),
                        pl.col("value").cast(pl.String),
                        pl.lit(self._(f"survey_choices_validator.issue.{question_suffix}")).alias(
                            "issue"
                        ),
                    ]
                )
                return difference_df

        results: list[ValidationResult] = []
        # kobo quesiton types to find
        column_selector = r"select_one|select_multiple"
        # pre-validation
        missing_choices: list[dict[str, str]] = []
        missing_binary_quesitons: list[dict[str, str]] = []
        value_difference_suffix = "value_has_difference"
        binary_value_difference_suffix = "binary_value_has_difference"

        results_df: pl.DataFrame = pl.DataFrame(
            [
                pl.Series("uuid", [], dtype=pl.String),
                pl.Series("sheet", [], dtype=pl.String),
                pl.Series("question", [], dtype=pl.String),
                pl.Series("value", [], dtype=pl.Int32),
                pl.Series("issue", [], dtype=pl.String),
            ]
        )

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.survey_sheet, self.choices_sheet, *self.check_sheets],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, data_loaded_columns = get_data_loaded_columns(
            data={
                self.survey_type_column: data_loaded_sheets[self.survey_sheet],
                self.survey_name_column: data_loaded_sheets[self.survey_sheet],
                self.choices_name_column: data_loaded_sheets[self.choices_sheet],
                self.choices_list_name_column: data_loaded_sheets[self.choices_sheet],
            },
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        filtered_loaded_sheets = filter_loaded_sheets(self.check_sheets, data_loaded_sheets)
        result, data_id_columns = get_data_sheet_ids(
            schema=self.schema, data=filtered_loaded_sheets, rule=self.name
        )

        if result:
            results.extend(result)
            return results

        # get the choices and turn it into a dict
        choices_dict = (
            data_loaded_sheets[self.choices_sheet]
            .data.select(
                [
                    pl.col(
                        data_loaded_columns[self.choices_list_name_column].data_column_name
                    ).str.strip_chars(" "),
                    pl.col(data_loaded_columns[self.choices_name_column].data_column_name)
                    .str.to_lowercase()
                    # .str.replace("_", "", literal=True)
                    .str.strip_chars(" "),
                ]
            )
            .filter(
                pl.col(
                    data_loaded_columns[self.choices_list_name_column].data_column_name
                ).is_not_null()
                & (
                    pl.col(data_loaded_columns[self.choices_list_name_column].data_column_name)
                    != ""
                )
            )
            .group_by(data_loaded_columns[self.choices_list_name_column].data_column_name)
            .agg(
                v_list=pl.col(
                    data_loaded_columns[self.choices_name_column].data_column_name
                ).implode()
            )
            .with_columns(pl.col("v_list").alias("values"))
            .select(
                [
                    data_loaded_columns[self.choices_list_name_column].data_column_name,
                    "values",
                ]
            )
            .to_dicts()
        )

        choices_dict = {
            row[data_loaded_columns[self.choices_list_name_column].data_column_name]: row["values"]
            for row in choices_dict
        }

        # get the survey questions that are selected from a list
        # and transform the data
        survey_category_questions_df = (
            data_loaded_sheets[self.survey_sheet]
            .data.select(
                [
                    data_loaded_columns[self.survey_type_column].data_column_name,
                    data_loaded_columns[self.survey_name_column].data_column_name,
                ]
            )
            .filter(
                pl.col(data_loaded_columns[self.survey_type_column].data_column_name).str.contains(
                    column_selector
                )
            )
            .with_columns(
                pl.col(data_loaded_columns[self.survey_type_column].data_column_name)
                .str.replace(r"[\"']", "")
                .str.strip_chars(" ")
                .str.split(" ")
                .list.to_struct(fields=["type_only", "choice_list_name"])
                .alias("choice_list_name")
            )
            .unnest("choice_list_name")
            .filter(pl.col("choice_list_name").is_not_null() & (pl.col("choice_list_name") != ""))
        )
        # split out the question types
        survey_category_questions_select_one = (
            survey_category_questions_df.filter(pl.col("type_only") == "select_one")
            .select([data_loaded_columns[self.survey_name_column].data_column_name])
            .unique()
            .to_series()
            .str.to_lowercase()
            .to_list()
        )

        survey_category_questions_select_multiple = (
            survey_category_questions_df.filter(pl.col("type_only") == "select_multiple")
            .select([data_loaded_columns[self.survey_name_column].data_column_name])
            .unique()
            .to_series()
            .str.to_lowercase()
            .to_list()
        )
        survey_question_choices_dict = survey_category_questions_df.select(
            [
                pl.col(
                    data_loaded_columns[self.survey_name_column].data_column_name
                ).str.to_lowercase(),
                "choice_list_name",
            ]
        ).to_dicts()

        survey_question_choices_dict = {
            row[data_loaded_columns[self.survey_name_column].data_column_name]: row[
                "choice_list_name"
            ]
            for row in survey_question_choices_dict
        }

        for sheet in self.check_sheets:
            filtered_questions_binary: list[str] = []
            check_sheet_id_column = data_id_columns[sheet][0]
            # only check the questions that are present on the sheet
            filtered_questions_select_one: list[str] = match_list(
                survey_category_questions_select_one,
                data_loaded_sheets[sheet].data.columns,
            )
            filtered_questions_select_multiple: list[str] = match_list(
                survey_category_questions_select_multiple,
                data_loaded_sheets[sheet].data.columns,
            )
            filtered_questions = filtered_questions_select_one + filtered_questions_select_multiple

            value_difference_expressions: list[pl.Expr] = []
            binary_value_difference_expressions: list[pl.Expr] = []

            # build an expression to find values that dont match
            # for each question, compare the values in the survey choices
            # to the values in the data sheet.
            # currently leading/trailing spaces are replaced and the
            # values are made lowercase.

            # because multiple_select questions store data as a space delimited values,
            # these values need to be split and compared individually.
            # in the event that a survey choice option has a space in it this process
            # will throw an error for the value being checked
            #
            # This step also checks the binary columns - they must be a 0 or 1 and
            # must also match the parent column

            for question in filtered_questions_select_multiple:
                try:
                    valid_choices: list[str] = choices_dict[survey_question_choices_dict[question]]
                except KeyError:
                    missing_choices.append(
                        {
                            "sheet": sheet,
                            "question": question,
                            "value": survey_question_choices_dict[question],
                            "issue": self._(
                                "survey_choices_validator.missing_choices.issue",
                                sheet=self.choices_sheet,
                            ),
                        }
                    )
                    filtered_questions.remove(question)
                    continue

                question_data_type = data_loaded_sheets[sheet].data.schema.get(question)
                if question_data_type is not None:
                    valid_choices = normalise_list(valid_choices, question_data_type)

                empty_question_column_expression = (
                    pl.col(question).fill_null("").str.strip_chars().is_in(["", None])
                )

                # expression to compare data values and choices values
                value_difference_expression = (
                    pl.when(empty_question_column_expression.not_())
                    .then(
                        pl.col(question)
                        .cast(pl.String)
                        .str.split(self.select_multiple_value_separator)
                        .list.eval(
                            pl.element()
                            .fill_null("")
                            .str.to_lowercase()
                            # .str.replace("_", "", literal=True)
                            .str.strip_chars(" ")
                            .is_in(valid_choices)
                            .not_()
                        )
                        .list.any()
                    )
                    .otherwise(False)
                    .alias(f"{question}_{value_difference_suffix}")
                )

                value_difference_expressions.append(value_difference_expression)

                # build list of binary columns
                questions_binary = [f"{question}.{choice}".lower() for choice in valid_choices]

                for question_binary in questions_binary:
                    if question_binary not in data_loaded_sheets[sheet].data.columns:
                        # check if column exists
                        missing_binary_quesitons.append(
                            {
                                "sheet": sheet,
                                "question": question,
                                "value": question_binary,
                                "issue": self._(
                                    "survey_choices_validator.missing_binary_questions.issue",
                                ),
                            }
                        )
                        continue

                    filtered_questions_binary.append(question_binary)
                    choice_name: str = question_binary.replace(f"{question}.", "").strip().lower()
                    question_to_list_expression = (
                        pl.col(question)
                        .cast(pl.String)
                        .str.split(self.select_multiple_value_separator)
                        .list.eval(
                            pl.element().fill_null("").str.to_lowercase().str.strip_chars(" ")
                        )
                        .list
                    )
                    binary_question_expression_base = (
                        pl.col(question_binary).cast(pl.String).fill_null("").str.strip_chars()
                    )

                    # binary column should be 1 or 0 if the parent column has a value
                    # binary and parent columns should match.
                    binary_value_difference_expression = (
                        # when parent is empty then binary column should be empty
                        pl.when(empty_question_column_expression)
                        .then(
                            # this currently means that the binary columns can either be blank or
                            # all 0's if the parent is empty
                            ~binary_question_expression_base.is_in(["", None, "0", "0.0"])
                        )
                        .otherwise(
                            # when binary column has a valid value then that
                            # value should be reflected in the parent
                            # if binary column has an invalid value or is not
                            # reflected in the parent then this will return a difference
                            pl.when(binary_question_expression_base.is_in(["0", "1", "0.0", "1.0"]))
                            .then(
                                pl.when(binary_question_expression_base.is_in(["1", "1.0"]))
                                # binary value not in parent
                                .then(question_to_list_expression.contains(choice_name).not_())
                                # binary value incorrectly in parent
                                .otherwise(question_to_list_expression.contains(choice_name))
                            )
                            .otherwise(True)
                        )
                        .alias(f"{question_binary}_{binary_value_difference_suffix}")
                    )
                    binary_value_difference_expressions.append(binary_value_difference_expression)

            # build an expression to find values that dont match
            # for each question, compare the values in the survey choices
            # to the values in the data sheet.
            # currently leading/trailing spaces are replaced and the
            # values are made lowercase.

            # choice values with spaces should not cause errors in this check

            for question in filtered_questions_select_one:
                try:
                    valid_choices: list[str] = choices_dict[survey_question_choices_dict[question]]
                except KeyError:
                    missing_choices.append(
                        {
                            "sheet": sheet,
                            "question": question,
                            "value": survey_question_choices_dict[question],
                            "issue": self._(
                                "survey_choices_validator.missing_choices.issue",
                                sheet=self.choices_sheet,
                            ),
                        }
                    )

                    filtered_questions.remove(question)
                    continue

                question_data_type = data_loaded_sheets[sheet].data.schema.get(question)
                if question_data_type is not None:
                    valid_choices = normalise_list(valid_choices, question_data_type)

                difference_expression = (
                    pl.when(
                        pl.col(question).fill_null("").str.strip_chars().is_in(["", None]).not_()
                    )
                    .then(
                        pl.col(question)
                        .cast(pl.String)
                        .fill_null("")
                        .str.to_lowercase()
                        # .str.replace("_", "", literal=True)
                        .str.strip_chars(" ")
                        .is_in(valid_choices)
                        .not_()
                    )
                    .otherwise(False)
                    .alias(f"{question}_{value_difference_suffix}")
                )

                value_difference_expressions.append(difference_expression)

            # calculate the actual differences from the built expressions
            value_difference_df = _get_difference(
                value_difference_expressions, value_difference_suffix, filtered_questions
            )
            if value_difference_df is not None:
                results_df = pl.concat([results_df, value_difference_df], how="vertical_relaxed")

            # calculate the actual binary differences from the built expressions
            if binary_value_difference_expressions:
                binary_value_difference_df = _get_difference(
                    binary_value_difference_expressions,
                    binary_value_difference_suffix,
                    filtered_questions_binary,
                )

                if binary_value_difference_df is not None:
                    results_df = pl.concat(
                        [results_df, binary_value_difference_df], how="vertical_relaxed"
                    )

        if results_df.height > 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "survey_choices_validator.invalid_values",
                        count=results_df.height,
                        choices_sheet=self.choices_sheet,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=results_df.to_dict(as_series=False),
                )
            )

        if missing_choices:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "survey_choices_validator.missing_choices",
                        count=len(missing_choices),
                        survey_sheet=self.survey_sheet,
                        choices_sheet=self.choices_sheet,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=pl.DataFrame(missing_choices).to_dict(as_series=False),
                )
            )

        if missing_binary_quesitons:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "survey_choices_validator.missing_binary_questions",
                        count=len(missing_binary_quesitons),
                    ),
                    severity=SeverityLevel.ERROR,
                    details=pl.DataFrame(missing_binary_quesitons).to_dict(as_series=False),
                )
            )

        return results
