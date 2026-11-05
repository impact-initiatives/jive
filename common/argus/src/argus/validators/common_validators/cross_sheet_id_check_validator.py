from typing import override

import polars as pl

from ...config import settings
from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base import SheetClassification
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_sheet,
    get_data_loaded_sheets,
    get_id_linking_columns,
)
from ..helpers.schema_helpers import get_schema_loaded_sheet


class CrossSheetIdCheck(BaseValidator):
    def __init__(
        self,
        schema: BaseDatasetSchema,
        master_sheet: str = "raw_data",
        child_sheets: list[str] | None = None,
        is_in: bool = True,
        exclude_id_values: list[str] | None = None,
    ):
        """Checks to see if ids from child sheet/s are present in a master/parent sheet

        Args:
            schema (BaseDatasetSchema): dataset schema
            master_sheet (str, optional): Sheet to make sure that child ids are in.
                Defaults to 'raw_data'.
            child_sheets (List, optional): Sheet/s to make sure that ids are in
                master_sheet. Defaults to ['clean_data', 'deletion_log', 'cleaning_log']
            is_in (bool, optional): determins if the child ids should (true) or
                should not (false) be in the matser sheet
            exclude_id_values (list[str] | None): excludes uuid records from a child sheet from
                the checks. Currently used for filtering out "all" from the cleaning log.
                Defaults to ["all"]
        """
        self.master_sheet: str = master_sheet
        self.child_sheets: list[str] = (
            child_sheets
            if child_sheets is not None
            else ["clean_data", "deletion_log", "cleaning_log"]
        )
        self.schema: BaseDatasetSchema = schema
        self.is_in: bool = is_in
        # used to filter out "all" in the cleaning log id column, for example
        self.exclude_id_values: list[str] = (
            exclude_id_values if exclude_id_values is not None else ["all"]
        )

    @property
    @override
    def name(self) -> str:
        return "CrossSheetIdCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if ids from child sheet/s are present in a master/parent sheet

            this process assumes that:
                -if both sheets have a unique column then these should be compared
                -if one sheet does not have a unique id column then a match is attempted
                based on schema name.
        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []

        if self.is_in:
            join_type = "anti"
            issue_message = self._("cross_sheet_id_check_validator.id_check_isnotin.issue")
        else:
            join_type = "semi"
            issue_message = self._("cross_sheet_id_check_validator.id_check_isin.issue")

        # join_type = "anti" if self.is_in else "semi"

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data, sheet_names=[self.master_sheet], rule=self.name
        )

        if result is not None:
            results.append(result)
            return results

        for sheet in self.child_sheets:
            result, child_loaded_sheet = get_data_loaded_sheet(
                data, sheet, self.name, check_data=False
            )

            if result is not None:
                results.append(result)
                continue
            assert child_loaded_sheet is not None

            if child_loaded_sheet.data.height < 1:
                # no data in sheet. eg empty deletion log
                continue

            result, child_schema_sheet = get_schema_loaded_sheet(
                self.schema, child_loaded_sheet.schema_sheet_name, self.name
            )
            if result is not None:
                results.append(result)
                continue

            assert child_schema_sheet is not None

            result, child_data_id_columns, master_id_columns = get_id_linking_columns(
                schema=self.schema,
                data_loaded_sheets=data_loaded_sheets | {sheet: child_loaded_sheet},
                source_sheet=sheet,
                target_sheet=self.master_sheet,
                rule=self.name,
                min_overlap=settings.MIN_COLUMN_MATCHING_OVERLAP if self.is_in else 0.0,
                exclude_id_values=self.exclude_id_values,
            )
            results.extend(result)
            if child_data_id_columns is None or master_id_columns is None:
                return results
            assert child_data_id_columns is not None
            assert master_id_columns is not None

            # filter id column. should only actually filter anything if the sheet
            # is a cleaning log sheet as it contains ids from multiple
            # clean data sheets (loops)
            missing_ids = (
                child_loaded_sheet.data.select(
                    pl.col(child_data_id_columns.data_column_name).cast(pl.String)
                )
                .filter(
                    (
                        pl.col(child_data_id_columns.data_column_name)
                        .str.strip_chars(" ")
                        .is_not_null()
                    )
                    & (pl.col(child_data_id_columns.data_column_name).str.strip_chars(" ") != "")
                    & (
                        (
                            (
                                pl.col(child_data_id_columns.data_column_name)
                                .is_in(self.exclude_id_values)
                                .not_()
                            )
                            & (
                                child_schema_sheet.classification
                                in [SheetClassification.CLEANING_LOG_SHEET]
                            )
                        )
                        | (
                            child_schema_sheet.classification
                            not in [SheetClassification.CLEANING_LOG_SHEET]
                        )
                    )
                )
                .join(
                    other=data_loaded_sheets[self.master_sheet].data.select(
                        pl.col(master_id_columns.data_column_name).cast(pl.String)
                    ),
                    how=join_type,
                    left_on=child_data_id_columns.data_column_name,
                    right_on=master_id_columns.data_column_name,
                )
                .to_series()
                .unique()
                .to_list()
            )
            if missing_ids:
                missing_df = pl.DataFrame({"uuid": missing_ids}).with_columns(
                    [
                        pl.lit(child_data_id_columns.data_column_name).alias("uuid_column_name"),
                        pl.lit(child_loaded_sheet.data_sheet_name).alias("source_sheet"),
                        pl.lit(data_loaded_sheets[self.master_sheet].data_sheet_name).alias(
                            "target_sheet"
                        ),
                        pl.lit(issue_message).alias("issue"),
                    ]
                )

                results.append(
                    ValidationResult(
                        rule=self.name,
                        message=self._(
                            "cross_sheet_id_check_validator.id_check_isnotin"
                            if self.is_in
                            else "cross_sheet_id_check_validator.id_check_isin",
                            count=len(missing_ids),
                            child_sheet=child_loaded_sheet.data_sheet_name,
                            child_column=child_data_id_columns.data_column_name,
                            master_sheet=data_loaded_sheets[self.master_sheet].data_sheet_name,
                            master_column=master_id_columns.data_column_name,
                        ),
                        severity=SeverityLevel.ERROR,
                        sheet_name=child_loaded_sheet.data_sheet_name,
                        column_name=child_data_id_columns.data_column_name,
                        details=missing_df.to_dict(as_series=False),
                    )
                )

        return results
