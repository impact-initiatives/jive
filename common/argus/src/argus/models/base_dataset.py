from pathlib import Path

import polars as pl

from ..common.list_matching import duplicate_list_items, filter_list, unique_list
from ..config import settings
from ..loaders.base_excel_loader import ExcelLoaderData
from ..locales.il8n import _
from ..models.base import SheetClassification
from ..validators.base import BaseValidator, SeverityLevel, SortedSheets, ValidationResult
from ..validators.common_validators import (
    CleaningLogToCleanCheck,
    ConsentCheck,
    CrossSheetIdCheck,
    CrossSheetRowSumCheck,
    DataTypeCheck,
    NaNDataCheck,
    RawToCleanToLogCheck,
    SkipLogicCheck,
    SurveyChoicesCheck,
)
from .base_dataset_schemas import BaseDatasetSchema
from .resolver import ResolveDataset


class BaseDataset:
    def __init__(self, schema_path: Path | str, validator_path: Path | str) -> None:
        self.schema_path: Path | str = schema_path
        self.validator_path: Path | str = validator_path
        self.resolver: ResolveDataset = ResolveDataset()
        self.schema: BaseDatasetSchema = self.get_schema()
        self.validators: list[BaseValidator] = self.get_validators()
        self.data: ExcelLoaderData
        self.sorted_sheets: SortedSheets = SortedSheets()

    def get_schema(self) -> BaseDatasetSchema:
        schema = self.resolver.resolve_schema(self.schema_path)
        return schema

    def get_validators(self) -> list[BaseValidator]:
        return self.resolver.resolve_validators(self.validator_path, self.schema)

    def process_data(self, **kwargs: int | str | float | Path) -> list[ValidationResult]:
        return []

    def build_validators(self):
        """
        Build all the sheet specific common validators.
        This assumes all the relationships are properly defined
        in the schema.
        """
        parent_clean_sheet = None
        self._sort_sheets()

        for sheet in self.schema.loaded_sheets:
            if (
                sheet.classification == SheetClassification.CLEANING_LOG_SHEET
                and sheet.parent_sheet is not None
            ):
                # cleaning log in clean
                self.validators.append(
                    CrossSheetIdCheck(
                        schema=self.schema,
                        master_sheet=sheet.parent_sheet,
                        child_sheets=[sheet.standard_name],
                    )
                )

                self.validators.append(
                    CleaningLogToCleanCheck(
                        schema=self.schema,
                        cleaning_log_sheet=sheet.standard_name,
                        clean_data_sheet=sheet.parent_sheet,
                    )
                )

                log_parent_clean_sheet = self.schema.get_schema_loaded_sheet(sheet.parent_sheet)

                # clean sheet and its linked raw sheet
                if (
                    log_parent_clean_sheet is not None
                    and log_parent_clean_sheet.linked_sheet is not None
                ):
                    self.validators.append(
                        RawToCleanToLogCheck(
                            schema=self.schema,
                            cleaning_log_sheet=sheet.standard_name,
                            clean_data_sheet=sheet.parent_sheet,
                            raw_data_sheet=log_parent_clean_sheet.linked_sheet,
                        )
                    )

            if sheet.classification == SheetClassification.DELETION_LOG_SHEET:
                if sheet.parent_sheet is not None:
                    parent_raw_sheet = self.schema.get_schema_loaded_sheet(sheet.parent_sheet)
                    if parent_raw_sheet is not None and parent_raw_sheet.linked_sheet is not None:
                        self.validators.append(
                            CrossSheetRowSumCheck(
                                schema=self.schema,
                                master_sheet=parent_raw_sheet.standard_name,
                                child_sheets=[parent_raw_sheet.linked_sheet, sheet.standard_name],
                                master_deletion_log=None,
                            )
                        )
                        # clean and deletion log in raw
                        self.validators.append(
                            CrossSheetIdCheck(
                                schema=self.schema,
                                master_sheet=parent_raw_sheet.standard_name,
                                child_sheets=[parent_raw_sheet.linked_sheet, sheet.standard_name],
                            )
                        )

                        clean_sheet = self.schema.get_schema_loaded_sheet(
                            parent_raw_sheet.linked_sheet
                        )
                        if clean_sheet is not None and clean_sheet.linked_log is not None:
                            # cleaning log not in deletion log
                            self.validators.append(
                                CrossSheetIdCheck(
                                    schema=self.schema,
                                    master_sheet=clean_sheet.linked_log,
                                    child_sheets=[sheet.standard_name],
                                    is_in=False,
                                )
                            )

            elif sheet.classification == SheetClassification.CLEAN_DATA_SHEET:
                # child in parent
                if sheet.parent_sheet is not None:
                    self.validators.append(
                        CrossSheetIdCheck(
                            schema=self.schema,
                            master_sheet=sheet.parent_sheet,
                            child_sheets=[sheet.standard_name],
                        )
                    )
                else:
                    # all child sheets should have the same parent
                    parent_clean_sheet = sheet.standard_name

            elif sheet.classification == SheetClassification.RAW_DATA_SHEET:
                # child in parent
                if sheet.parent_sheet is not None:
                    self.validators.append(
                        CrossSheetIdCheck(
                            schema=self.schema,
                            master_sheet=sheet.parent_sheet,
                            child_sheets=[sheet.standard_name],
                        )
                    )

                if sheet.parent_sheet is None and sheet.linked_sheet is not None:
                    self.validators.append(
                        ConsentCheck(
                            schema=self.schema,
                            raw_data_sheet=sheet.standard_name,
                            clean_data_sheet=sheet.linked_sheet,
                        )
                    )

        if self.sorted_sheets.clean_sheets:
            self.validators.append(
                NaNDataCheck(schema=self.schema, check_sheets=self.sorted_sheets.clean_sheets)
            )

            if self.schema.get_schema_loaded_sheet(settings.SURVEY_SHEET_NAME) is not None:
                self.validators.append(
                    DataTypeCheck(schema=self.schema, check_sheets=self.sorted_sheets.clean_sheets)
                )

                if parent_clean_sheet is not None:
                    self.validators.append(
                        SkipLogicCheck(
                            schema=self.schema,
                            parent_sheet=parent_clean_sheet,
                            child_sheets=filter_list(
                                self.sorted_sheets.clean_sheets, [parent_clean_sheet]
                            ),
                        )
                    )

                if self.schema.get_schema_loaded_sheet(settings.CHOICES_SHEET_NAME) is not None:
                    self.validators.append(
                        SurveyChoicesCheck(
                            schema=self.schema, check_sheets=self.sorted_sheets.clean_sheets
                        )
                    )

    def _sort_sheets(self):

        self.sorted_sheets = SortedSheets()

        for sheet in self.schema.loaded_sheets:
            if sheet.classification == SheetClassification.CLEANING_LOG_SHEET:
                self.sorted_sheets.cleaning_log_sheets.append(sheet.standard_name)
            if sheet.classification == SheetClassification.DELETION_LOG_SHEET:
                self.sorted_sheets.deletion_log_sheets.append(sheet.standard_name)
            elif sheet.classification == SheetClassification.CLEAN_DATA_SHEET:
                self.sorted_sheets.clean_sheets.append(sheet.standard_name)
            elif sheet.classification == SheetClassification.RAW_DATA_SHEET:
                self.sorted_sheets.raw_sheets.append(sheet.standard_name)
            elif sheet.classification == SheetClassification.UNKNOWN:
                self.sorted_sheets.unknown_sheets.append(sheet.standard_name)

    def validate_schema_links(self):
        """Checks all the sheet linkages in the schema to make
        sure they are all defined properly. It currently only checks
        that there is a link when there should be one.

        See SchemaSheetMap for the expected structure.

        TODO: it would be possible to expand this further by checking
        recipricol relationships. E.g: the raw_data linking sheet for a clean_data
        sheet should list the clean_data sheet as its linking sheet.

        Note: build_validators should be called before this is used
        as this step assumes that _sort_sheets has already been run.

        Returns any unexpected/missing links as errors.
        """
        results: list[ValidationResult] = []
        rule = "SchemaValidation_SheetLinks"

        def _check_links(
            sheet_classification: SheetClassification,
            property_name: str,
            sheet_type: str,
            linked_sheet_type: str,
            issue: str,
            issue_key: str,
            min_items: int = 0,
        ):
            """check for unlinked/matched sheets"""
            items = [
                item.standard_name
                for item in self.schema.loaded_sheets
                if item.classification == sheet_classification
                and getattr(item, property_name) is None
            ]
            if len(items) > min_items:
                results.append(
                    ValidationResult(
                        rule=rule,
                        message=_(
                            f"base_dataset.validate_schema.{issue_key}",
                            count=len(items),
                            sheet_type=sheet_type,
                            linked_sheet_type=linked_sheet_type,
                        ),
                        severity=SeverityLevel.ERROR,
                        details=pl.DataFrame({"sheet": items})
                        .with_columns(pl.lit(issue).alias("issue"))
                        .to_dict(as_series=False),
                    )
                )

        def _check_parents(sheet_classification: SheetClassification, sheet_type: str):
            """Checks that clean or raw data sheets only have at most one parent"""
            items = [
                item.parent_sheet
                for item in self.schema.loaded_sheets
                if item.classification == sheet_classification and item.parent_sheet is not None
            ]
            unique_items = unique_list(items)
            if len(unique_items) > 1:
                results.append(
                    ValidationResult(
                        rule=rule,
                        message=_(
                            "base_dataset.validate_schema.multiple_parents",
                            count=len(unique_items),
                            sheet_type=sheet_type,
                            parents=", ".join(unique_items),
                        ),
                        severity=SeverityLevel.ERROR,
                    )
                )

        if self.sorted_sheets.clean_sheets:
            # should only be one sheet without a parent
            _check_links(
                SheetClassification.CLEAN_DATA_SHEET,
                "parent_sheet",
                "clean_data",
                "",
                _("base_dataset.validate_schema.no_parent.issue"),
                "no_parent",
                1,
            )

            # sheets should only link to one parent
            _check_parents(SheetClassification.CLEAN_DATA_SHEET, "clean_data")

            if self.sorted_sheets.raw_sheets:
                # clean sheets should link to a raw sheet
                _check_links(
                    SheetClassification.CLEAN_DATA_SHEET,
                    "linked_sheet",
                    "clean_data",
                    "raw_data",
                    _("base_dataset.validate_schema.missing_links.issue", sheet="raw_data"),
                    "missing_links",
                )

            if self.sorted_sheets.cleaning_log_sheets:
                # clean sheets should link to a cleaning log sheet
                _check_links(
                    SheetClassification.CLEAN_DATA_SHEET,
                    "linked_log",
                    "clean_data",
                    "cleaning_log",
                    _("base_dataset.validate_schema.missing_links.issue", sheet="cleaning_log"),
                    "missing_links",
                )

        if self.sorted_sheets.raw_sheets:
            # should only be one sheet without a parent
            _check_links(
                SheetClassification.RAW_DATA_SHEET,
                "parent_sheet",
                "raw_data",
                "",
                _("base_dataset.validate_schema.no_parent.issue"),
                "no_parent",
                1,
            )

            # sheets should only link to one parent
            _check_parents(SheetClassification.RAW_DATA_SHEET, "raw_data")

            if self.sorted_sheets.clean_sheets:
                # clean sheets should link to a raw sheet
                _check_links(
                    SheetClassification.RAW_DATA_SHEET,
                    "linked_sheet",
                    "raw_data",
                    "clean_data",
                    _("base_dataset.validate_schema.missing_links.issue", sheet="clean_data"),
                    "missing_links",
                )

            if self.sorted_sheets.deletion_log_sheets:
                # raw sheets should link to a deletion log sheet
                _check_links(
                    SheetClassification.RAW_DATA_SHEET,
                    "linked_log",
                    "raw_data",
                    "deletion_log",
                    _("base_dataset.validate_schema.missing_links.issue", sheet="deletion_log"),
                    "missing_links",
                )

        if self.sorted_sheets.deletion_log_sheets:
            # deletion_log sheets should link to a raw data sheet
            _check_links(
                SheetClassification.DELETION_LOG_SHEET,
                "parent_sheet",
                "deletion_log",
                "raw_data",
                _("base_dataset.validate_schema.missing_links.issue", sheet="raw_data"),
                "missing_links",
            )

        if self.sorted_sheets.cleaning_log_sheets:
            # cleaning_log sheets should link to a clean_data sheet
            _check_links(
                SheetClassification.CLEANING_LOG_SHEET,
                "parent_sheet",
                "cleaning_log",
                "clean_data",
                _("base_dataset.validate_schema.missing_links.issue", sheet="clean_data"),
                "missing_links",
            )
        return results

    def validate_schema_item_names(self) -> list[ValidationResult]:
        """Checks that a sheet is listed only once in the schema.

        Checks that a column is listed only once per sheet. This check
        does not include unique columns as they are likely included
        in mandatory columns and only one unique column can be set

        Returns:
            List[ValidationResult]: validation errors
        """
        sheet_names: list[str] = []
        results: list[ValidationResult] = []

        for sheet in self.schema.loaded_sheets:
            sheet_names.extend(sheet.combine_sheet_names())
            column_names: list[str] = sheet.combine_column_names(return_unique_list=False)

            # check duplicate columns per sheet
            duplicate_column_names = duplicate_list_items(column_names)
            if duplicate_column_names:
                results.append(
                    ValidationResult(
                        rule="SchemaValidation_DuplicateColumnNames",
                        message=f" Sheet {sheet} for schema {self.schema.programme_type} "
                        + f"{self.schema.output_type} has mandatory column standard/altername names"
                        + " listed on more than one column. Column names should be unique per sheet"
                        + ". Check the output for details.",
                        severity=SeverityLevel.ADMIN_ERROR,
                        column_name=", ".join(duplicate_column_names),
                        details={"columns": duplicate_column_names},
                    )
                )
        for sheet in self.schema.unloaded_sheets:
            sheet_names.extend(sheet.combine_sheet_names())

        duplicate_sheet_names = duplicate_list_items(sheet_names)
        if duplicate_sheet_names:
            results.append(
                ValidationResult(
                    rule="SchemaValidation_DuplicateSheetNames",
                    message=f"The schema for {self.schema.programme_type} {self.schema.output_type}"
                    + " contains sheet names that are listed for more than one sheet. Sheet names"
                    + " and alternate sheet names should be unique to each schema."
                    + " Check the output for details.",
                    severity=SeverityLevel.ADMIN_ERROR,
                    details={"sheets": duplicate_sheet_names},
                )
            )

        return results
