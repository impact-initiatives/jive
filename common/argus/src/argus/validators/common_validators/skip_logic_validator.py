from typing import override

import polars as pl

from ...common.list_matching import combine_lists, filter_loaded_sheets, match_list
from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_columns,
    get_data_loaded_sheets,
    get_data_sheet_ids,
    get_id_linking_columns,
)
from ..helpers.skip_logic_parser import build_relevance_expression, get_all_references, is_missing


class SkipLogicCheck(BaseValidator):
    def __init__(
        self,
        schema: BaseDatasetSchema,
        survey_sheet: str = settings.SURVEY_SHEET_NAME,
        survey_relevant_column: str = "relevant",
        survey_required_column: str = "required",
        survey_name_column: str = "name",
        parent_sheet: str = "clean_data",
        child_sheets: list[str] | None = None,
    ) -> None:
        """

        Args:
            schema (BaseDatasetSchema): dataset schema
            survey_sheet (str, optional): name of the kobo survey sheet.
                Defaults to 'survey'.
            survey_relevant_column (str, optional): name of the relevant column in the
                kobo survey sheet. Defaults to 'relevant'.
            survey_required_column: (str, optional):  name of the required column in the
                kobo survey sheet. Defaults to 'required'.
            survey_name_column (str, optional): name of the name column in the
                kobo survey sheet. Defaults to 'name'.
            parent_sheet (str): parent clean data sheet. Deffaults to 'clean_data'.
            child_sheets (list[str] | None): list of child clean data sheets to check, if any

        """
        self.schema: BaseDatasetSchema = schema
        self.survey_sheet: str = survey_sheet
        self.survey_relevant_column: str = survey_relevant_column
        self.survey_required_column: str = survey_required_column
        self.survey_name_column: str = survey_name_column
        self.child_sheets: list[str] | None = child_sheets
        self.parent_sheet: str = parent_sheet

    @property
    @override
    def name(self) -> str:
        return "SkipLogicCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks that clean_data columns/questions from the survey that contain skip logic
        contain:
        - no value when the question was skipped
        - a value when the question was not skipped and marked as required.

        This is done through converting kobo skip logic into polars expressions.

        Limitations:
        Support for cross sheet references is limited.
        This process only supports column references that are on
        a parent sheet (child referencing parent). If the reference is on a child sheet
        (parent reference to child) or between child sheets then
        any affected columns will produce a warning.

        Returns:
            list[ValidationResult]: a list of validation results, if any
        """

        results: list[ValidationResult] = []
        failed_conversions: list[dict[str, str]] = []

        all_issues_df: pl.DataFrame = pl.DataFrame(
            [
                pl.Series("sheet", [], dtype=pl.String),
                pl.Series("uuid_column", [], dtype=pl.String),
                pl.Series("uuid", [], dtype=pl.String),
                pl.Series("question", [], dtype=pl.String),
                pl.Series("issue", [], dtype=pl.String),
            ]
        )

        # check all the sheets exist
        check_sheets = [self.parent_sheet]
        if self.child_sheets:
            check_sheets.extend(self.child_sheets)

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data,
            sheet_names=[self.survey_sheet, *check_sheets],
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        result, data_loaded_columns = get_data_loaded_columns(
            data={
                self.survey_relevant_column: data_loaded_sheets[self.survey_sheet],
                self.survey_name_column: data_loaded_sheets[self.survey_sheet],
                self.survey_required_column: data_loaded_sheets[self.survey_sheet],
            },
            rule=self.name,
        )

        if result is not None:
            results.append(result)
            return results

        filtered_loaded_sheets = filter_loaded_sheets(check_sheets, data_loaded_sheets)
        result, data_id_columns = get_data_sheet_ids(
            schema=self.schema, data=filtered_loaded_sheets, rule=self.name
        )

        if result:
            results.extend(result)
            return results

        # filter survey sheet to get columns with skip logic
        survey_relevant_columns_df = (
            data_loaded_sheets[self.survey_sheet]
            .data.filter(
                pl.col(
                    data_loaded_columns[self.survey_relevant_column].data_column_name
                ).str.strip_chars()
                != ""
            )
            .select(
                [
                    pl.col(data_loaded_columns[self.survey_relevant_column].data_column_name),
                    pl.col(
                        data_loaded_columns[self.survey_name_column].data_column_name
                    ).str.to_lowercase(),
                    pl.col(data_loaded_columns[self.survey_required_column].data_column_name)
                    .cast(pl.String)
                    .str.to_lowercase(),
                ]
            )
        )

        # survey questions with skip logic
        survey_relevant_columns = (
            survey_relevant_columns_df.select(
                data_loaded_columns[self.survey_name_column].data_column_name
            )
            .to_series()
            .to_list()
        )

        if not survey_relevant_columns:
            return results

        # survey questions with skip logic marked as required if shown
        survey_relevant_required_columns = (
            survey_relevant_columns_df.filter(
                pl.col(data_loaded_columns[self.survey_required_column].data_column_name).is_in(
                    ["yes", "true"]
                )
            )
            .select(data_loaded_columns[self.survey_name_column].data_column_name)
            .to_series()
            .to_list()
        )

        # get all columns referenced in the expressions
        referenced_columns = get_all_references(
            survey_relevant_columns_df[
                data_loaded_columns[self.survey_relevant_column].data_column_name
            ].to_list()
        )

        for sheet in check_sheets:
            # get columns relevant for sheet
            check_columns = set(
                match_list(data_loaded_sheets[sheet].data.columns, survey_relevant_columns)
            )

            # columns referenced in the sheet
            check_referenced_columns = set(
                match_list(data_loaded_sheets[sheet].data.columns, referenced_columns)
            )

            # combine referenced columns and skip logic columns
            sheet_columns_needed = combine_lists(check_columns, check_referenced_columns)

            if not check_columns:
                continue

            check_required_columns = set(
                match_list(data_loaded_sheets[sheet].data.columns, survey_relevant_required_columns)
            )

            check_sheet_id_column = data_id_columns[sheet][0]

            if sheet != self.parent_sheet:
                parent_columns_referenced = match_list(
                    data_loaded_sheets[self.parent_sheet].data.columns, referenced_columns
                )
                if parent_columns_referenced:
                    # check if any parent columns are referenced. if so, join
                    # to the parent sheet getting only the required columns
                    result, child_sheet_linking_id_columns, parent_sheet_id_columns = (
                        get_id_linking_columns(
                            schema=self.schema,
                            data_loaded_sheets=data_loaded_sheets,
                            source_sheet=sheet,
                            target_sheet=self.parent_sheet,
                            rule=self.name,
                        )
                    )
                    results.extend(result)
                    if parent_sheet_id_columns is None or child_sheet_linking_id_columns is None:
                        # should be an error in result
                        continue
                    assert child_sheet_linking_id_columns is not None
                    assert parent_sheet_id_columns is not None

                    # filter the two dataframes to only contain the minimum required columns
                    data_df = (
                        data_loaded_sheets[sheet]
                        .data.select(
                            [
                                check_sheet_id_column.data_column_name,
                                child_sheet_linking_id_columns.data_column_name,
                                *sheet_columns_needed,
                            ]
                        )
                        .join(
                            data_loaded_sheets[self.parent_sheet].data.select(
                                [
                                    parent_sheet_id_columns.data_column_name,
                                    *parent_columns_referenced,
                                ]
                            ),
                            left_on=child_sheet_linking_id_columns.data_column_name,
                            right_on=parent_sheet_id_columns.data_column_name,
                        )
                    )
                else:
                    # select minimally required data
                    data_df = data_loaded_sheets[sheet].data.select(
                        [check_sheet_id_column.data_column_name, *sheet_columns_needed]
                    )
            else:
                data_df = data_loaded_sheets[sheet].data.select(
                    [check_sheet_id_column.data_column_name, *sheet_columns_needed]
                )

            expressions: dict[str, pl.Expr] = {}
            # build an expression for each relevant survey question
            # this only loops through the relevant survey rows so
            # using iter_rows is not too bad
            for row in survey_relevant_columns_df.iter_rows(named=True):
                if (
                    row[data_loaded_columns[self.survey_name_column].data_column_name]
                    not in check_columns
                ):
                    continue

                try:
                    expressions[
                        row[data_loaded_columns[self.survey_name_column].data_column_name]
                    ] = build_relevance_expression(
                        row[data_loaded_columns[self.survey_relevant_column].data_column_name],
                        data_df.schema,
                    )

                except Exception as e:
                    # most likely due to column references in other sheets but
                    # will also report errors with the expression builder
                    failed_conversions.append(
                        {
                            "sheet": sheet,
                            "question": row[
                                data_loaded_columns[self.survey_name_column].data_column_name
                            ],
                            "expression": row[
                                data_loaded_columns[self.survey_relevant_column].data_column_name
                            ],
                            "issue": str(e),
                        }
                    )
                    continue

            if not expressions:
                continue

            # useful for finind out which columns are causing errors in the
            # below select statements
            # df = data_loaded_sheets[sheet].data
            # for q, expr in expressions.items():
            #     if q not in check_columns:
            #         continue
            #     try:
            #         df.select(expr.alias(q))
            #     except Exception as e:
            #         print(f"OFFENDER: {q!r}\n  {type(e).__name__}: {e}")

            # values when there shouldnt be
            value_exist_df = (
                data_df.with_columns(
                    *(e.alias(q) for q, e in expressions.items() if q in check_columns),
                )
                .select(
                    [
                        check_sheet_id_column.data_column_name,
                        *(q for q in expressions if q in check_columns),
                    ]
                )
                .unpivot(
                    index=check_sheet_id_column.data_column_name,
                    value_name="shown",
                    variable_name=data_loaded_columns[self.survey_name_column].data_column_name,
                )
            )

            # no values when there should be if the field is required
            value_not_exist_df = (
                data_df.with_columns(
                    *(is_missing(q).alias(q) for q in expressions if q in check_columns),
                )
                .select(
                    [
                        check_sheet_id_column.data_column_name,
                        *(q for q in expressions if q in check_required_columns),
                    ]
                )
                .unpivot(
                    index=check_sheet_id_column.data_column_name,
                    value_name="missing",
                    variable_name=data_loaded_columns[self.survey_name_column].data_column_name,
                )
            )

            res = value_exist_df.join(
                value_not_exist_df,
                on=[
                    check_sheet_id_column.data_column_name,
                    data_loaded_columns[self.survey_name_column].data_column_name,
                ],
            ).join(
                survey_relevant_columns_df,
                on=data_loaded_columns[self.survey_name_column].data_column_name,
            )

            if res.height > 0:
                issues_df = (
                    res.filter(pl.col("shown") == pl.col("missing"))
                    .with_columns(
                        pl.when(pl.col("missing"))
                        .then(
                            pl.lit(self._("skip_logic_validator.invalid_values.issue.empty_value"))
                        )
                        .otherwise(
                            pl.lit(
                                self._("skip_logic_validator.invalid_values.issue.not_empty_value")
                            )
                        )
                        .alias("issue")
                    )
                    .select(
                        pl.lit(sheet).alias("sheet"),
                        pl.lit(check_sheet_id_column.data_column_name).alias("uuid_column"),
                        pl.col(check_sheet_id_column.data_column_name)
                        .cast(pl.String)
                        .alias("uuid"),
                        pl.col(data_loaded_columns[self.survey_name_column].data_column_name).alias(
                            "question"
                        ),
                        "issue",
                    )
                    .sort(["question"])
                )

                all_issues_df = pl.concat([all_issues_df, issues_df])

        if failed_conversions:
            # might have duplicates but not a big issue
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "skip_logic_validator.failed_conversions",
                        count=len(failed_conversions),
                    ),
                    severity=SeverityLevel.WARNING,
                    details=pl.DataFrame(failed_conversions).to_dict(as_series=False),
                )
            )

        if all_issues_df.height > 0:
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "skip_logic_validator.invalid_values",
                        count=all_issues_df.height,
                    ),
                    severity=SeverityLevel.ERROR,
                    details=all_issues_df.to_dict(as_series=False),
                )
            )

        return results
