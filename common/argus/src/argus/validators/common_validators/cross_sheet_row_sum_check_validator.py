from dataclasses import dataclass
from typing import override

from ...loaders.base_excel_loader import ExcelLoaderData
from ...models.base_dataset_schemas import BaseDatasetSchema
from ..base import BaseValidator, SeverityLevel, ValidationResult
from ..helpers.data_helpers import (
    get_data_loaded_sheets,
    get_data_sheet_id,
)
from ..helpers.schema_helpers import get_schema_loaded_sheet


class CrossSheetRowSumCheck(BaseValidator):
    def __init__(
        self,
        schema: BaseDatasetSchema,
        master_sheet: str = "raw_data",
        child_sheets: list[str] | None = None,
        master_deletion_log: str | None = None,
    ):
        """
        Checks to see if master_sheet rows equals the sum of child sheet rows

        Note:
        Using master_deletion_log can produce "incorrect" counts if there is only one deletion log
        for multiple clean/raw sheets when a child record has been deleted
        but the parent record was not deleted.

        Ideally, each clean/raw data sheet will have its own deletion log.

        Args:
            master_sheet (str, optional): Sheet to make sure that child ids are in.
                Defaults to 'raw_data'.
            child_sheets (List, optional): Sheet/s to make sure that ids are in
                master_sheet. Dont pass deletion log here if processing loops.
                Defaults to ['clean_data', 'deletion_log'].
            master_deletion_log (str, optional): if loops are being processed,
                specify the deletion log here to make sure the correct deletion count
                 is used. Dont pass it as a child sheet in this case.
        """
        self.schema: BaseDatasetSchema = schema
        self.master_sheet: str = master_sheet
        self.child_sheets: list[str] = (
            child_sheets if child_sheets is not None else ["clean_data", "deletion_log"]
        )
        self.master_deletion_log: str | None = master_deletion_log

    @property
    @override
    def name(self) -> str:
        return "CrossSheetRowSumCheck"

    @override
    def validate(
        self, data: ExcelLoaderData, **kwargs: str | int | float
    ) -> list[ValidationResult]:
        """Checks to see if master_sheet rows equals the sum of child sheet rows rows.

        Args:
            data (ExcelLoaderData): data to be validated

        Returns:
            List[ValidationResult]: List of validation errors.
        """
        results: list[ValidationResult] = []
        master_data_count: int = 0
        deleted_data_count: int | None = None

        @dataclass(slots=True)
        class ChildCounts:
            sheet_name: str
            row_count: int

        child_counts: list[ChildCounts] = []

        sheets_to_load = [self.master_sheet, *self.child_sheets]
        if self.master_deletion_log is not None:
            sheets_to_load.append(self.master_deletion_log)

        result, data_loaded_sheets = get_data_loaded_sheets(
            data=data, sheet_names=sheets_to_load, rule=self.name, check_data=False
        )
        if result is not None:
            results.append(result)
            return results

        # if this is a child sheet then just using the deletion log count will
        #  be inaccurate as  one deletion record could link to several child records.
        # join the deletion log to the childs parent id column to get a count of the
        # number of child records deleted.
        result, master_schema_sheet = get_schema_loaded_sheet(
            self.schema, self.master_sheet, self.name
        )
        if result is not None:
            # unlikely to happen as it would have to be matched to pass the previous
            # get_data_loaded_sheets check
            results.append(result)
            return results

        if master_schema_sheet is not None and (
            master_schema_sheet.parent_sheet is not None
            and master_schema_sheet.parent_linking_column is not None
            and self.master_deletion_log is not None
        ):
            if data_loaded_sheets[self.master_deletion_log].data.height < 1:
                child_counts.append(
                    ChildCounts(
                        sheet_name=self.master_deletion_log,
                        row_count=0,
                    )
                )
            else:
                result, data_sheet_ids = get_data_sheet_id(
                    schema=self.schema,
                    sheet_name=self.master_deletion_log,
                    loaded_sheet=data_loaded_sheets[self.master_deletion_log],
                    rule=self.name,
                )

                if result:
                    results.append(result)
                    return results
                data_sheet_ids = data_sheet_ids[0]

                deleted_data_count = (
                    data_loaded_sheets[self.master_deletion_log]
                    .data.join(
                        other=data_loaded_sheets[self.master_sheet].data,
                        left_on=data_sheet_ids.data_column_name,
                        right_on=master_schema_sheet.parent_linking_column,
                        how="inner",
                    )
                    .n_unique()
                )
                child_counts.append(
                    ChildCounts(
                        sheet_name=self.master_deletion_log,
                        row_count=deleted_data_count,
                    )
                )

        master_data_count = data_loaded_sheets[self.master_sheet].data.height

        for sheet in self.child_sheets:
            child_counts.append(
                ChildCounts(sheet_name=sheet, row_count=data_loaded_sheets[sheet].data.height)
            )

        child_sum = sum([item.row_count for item in child_counts])
        missing_rows: int = abs(child_sum - master_data_count)
        if missing_rows > 0:
            child_message = " and ".join(
                [f"{item.sheet_name} ({item.row_count})" for item in child_counts]
            )
            results.append(
                ValidationResult(
                    rule=self.name,
                    message=self._(
                        "cross_sheet_row_sum_check_validator.row_sum",
                        child_sheets=child_message,
                        master_sheet=self.master_sheet,
                        count_master=master_data_count,
                        count_diff=missing_rows,
                    ),
                    severity=SeverityLevel.ERROR,
                )
            )

        return results
