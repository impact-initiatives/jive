from dataclasses import dataclass, field

from argus.locales.il8n import _

from ..common.list_matching import (
    FuzzMatch,
    duplicate_list_items,
    filter_list,
    lower_list_items,
    match_list_to_list,
    unique_list,
)
from ..config import settings
from ..loaders.base import DataColumnMap, DataSheetMap
from ..models.base import SchemaSheetMap
from ..validators.base import SeverityLevel, ValidationResult


class BaseExcelLoader:
    def match_excel_columns_to_schema(
        self, excel_columns: list[str], schema_sheet: SchemaSheetMap
    ) -> tuple[list[ValidationResult], list[DataColumnMap]]:
        """trys to match an excel column to a schema column.

            First, a literal match is attempted. If one is found this
            is returned

            If there is no literal match and fuzzy matching is enabled
            then a fuzzy match is attempted. If a match is made to only
            one column then this is returned. If a match is made to more than
            one column then no match is returned.

        Args:
            excel_columns (List): list of escel columns
            schema_sheet (SchemaSheetMap): schema sheet to search against

        Returns:
            tuple[List[ValidationResult], List[DataColumnMap]]: _description_
        """
        results: list[ValidationResult] = []
        matches: list[DataColumnMap] = []

        excel_columns_filtered = filter_list(excel_columns, settings.IGNORE_COLUMNS_FOR_MATCHING)

        for column in schema_sheet.columns:
            literal_matches, fuzzy_matched_values = match_list_to_list(
                column.combine(), excel_columns_filtered, fuzzy_match=column.allow_fuzzy_matching
            )

            if literal_matches:
                if len(literal_matches) == 1:
                    # because the schema is prevalidated there should only
                    # be one literal match unless there are multiple alternate
                    # name matches
                    matches.append(
                        DataColumnMap(
                            data_column_name=literal_matches[0],
                            schema_column_name=column.standard_name,
                        )
                    )

                else:
                    # ideally this should not happen
                    results.append(
                        ValidationResult(
                            rule="Match excel column to schema",
                            message=self._(
                                "base_excel_loader.match_excel_columns_to_schema.multiple_literal_matches",
                                sheet=schema_sheet.standard_name,
                                column=column.standard_name,
                                count=len(literal_matches),
                            ),
                            severity=SeverityLevel.ERROR,
                            sheet_name=schema_sheet.standard_name,
                            column_name=column.standard_name,
                            details={"Literal Match Columns": literal_matches},
                        )
                    )
                continue
            elif fuzzy_matched_values:
                fuzzy_matched_columns = unique_list(
                    [key for item in fuzzy_matched_values for key in item.matches]
                )
                if len(fuzzy_matched_columns) == 1:
                    matches.append(
                        DataColumnMap(
                            data_column_name=fuzzy_matched_columns[0],
                            schema_column_name=column.standard_name,
                        )
                    )

                    results.append(
                        ValidationResult(
                            rule="Match excel column to schema",
                            message=self._(
                                "base_excel_loader.match_excel_columns_to_schema.fuzzy_match",
                                sheet=schema_sheet.standard_name,
                                column=column.standard_name,
                            ),
                            severity=SeverityLevel.INFO,
                            sheet_name=schema_sheet.standard_name,
                            column_name=column.standard_name,
                            details={column.standard_name: fuzzy_matched_values},
                        )
                    )
                else:
                    results.append(
                        ValidationResult(
                            rule="Match excel column to schema",
                            message=self._(
                                "base_excel_loader.match_excel_columns_to_schema.fuzzy_match_miltiple",
                                sheet=schema_sheet.standard_name,
                                column=column.standard_name,
                                count=len(fuzzy_matched_columns),
                            ),
                            severity=SeverityLevel.ERROR,
                            sheet_name=schema_sheet.standard_name,
                            column_name=column.standard_name,
                            details={column.standard_name: fuzzy_matched_values},
                        )
                    )
        return results, matches

    def match_excel_sheet_to_schema(
        self, excel_sheet_name: str, schema_sheets: list[SchemaSheetMap]
    ) -> tuple[str, list[ValidationResult]]:
        """Trys to match an excel sheet name to a schema sheet name.

            First, a literal match is attempted. If one is found this
            is returned

            If there is no literal match and fuzzy matching is enabled
            then a fuzzy match is attempted. If a match is made to only
            one sheet then this is returned. If a match is made to more than
            one sheet then no match is returned.
        Args:
            sheet_name (str): excel sheet to be matched
            schema_sheets (List[SheetMapping]): schema sheets to match to.

        Returns:
            tuple[str, List[ValidationResult]]: the schema sheet standard name
            if matched, a list of any validation warnings if relevant.
        """
        results: list[ValidationResult] = []
        fuzzy_matched_values_schema: dict[str, list[FuzzMatch]] = {}

        for sheet_config in schema_sheets:
            literal_matches, fuzzy_matched_values = match_list_to_list(
                sheet_config.combine_sheet_names(),
                [excel_sheet_name],
                fuzzy_match=sheet_config.allow_fuzzy_matching,
            )

            if literal_matches:
                # clear warning as they are not relevant if a literal match is found
                results = []
                return sheet_config.standard_name, results
            elif (
                sheet_config.matching_term
                and sheet_config.matching_term in excel_sheet_name
                and (
                    sheet_config.matching_term_ignore is None
                    or not any(
                        term in excel_sheet_name for term in sheet_config.matching_term_ignore
                    )
                )
            ):
                results.append(
                    ValidationResult(
                        rule="Match excel sheeet to schema",
                        message=self._(
                            "base_excel_loader.match_excel_sheet_to_schema.matching_term",
                            excel_sheet=excel_sheet_name,
                            schema_sheet=sheet_config.standard_name,
                            matching_term=sheet_config.matching_term,
                        ),
                        severity=SeverityLevel.INFO,
                        sheet_name=excel_sheet_name,
                    )
                )
                return sheet_config.standard_name, results
            elif fuzzy_matched_values:
                fuzzy_matched_values_schema[sheet_config.standard_name] = fuzzy_matched_values

        if bool(fuzzy_matched_values_schema):
            if len(fuzzy_matched_values_schema.keys()) == 1:
                # fuzzy match to only 1 schema sheet
                sheet_name = list(fuzzy_matched_values_schema.keys())[0]
                results.append(
                    ValidationResult(
                        rule="Match excel sheeet to schema",
                        message=self._(
                            "base_excel_loader.match_excel_sheet_to_schema.fuzzy_match",
                            excel_sheet=excel_sheet_name,
                            schema_sheet=sheet_name,
                        ),
                        severity=SeverityLevel.INFO,
                        sheet_name=excel_sheet_name,
                        details={excel_sheet_name: fuzzy_matched_values_schema},
                    )
                )
                return sheet_name, results
            else:
                # fuzzy match to multiple schema sheets
                results.append(
                    ValidationResult(
                        rule="Match excel sheeet to schema",
                        message=self._(
                            "base_excel_loader.match_excel_sheet_to_schema.fuzzy_match_multiple",
                            excel_sheet=excel_sheet_name,
                            count=len(fuzzy_matched_values_schema.keys()),
                        ),
                        severity=SeverityLevel.INFO,
                        sheet_name=excel_sheet_name,
                        details={excel_sheet_name: fuzzy_matched_values_schema},
                    )
                )

        return "", results

    def check_duplicate_columns(
        self, columns: list[str], sheet_name: str
    ) -> ValidationResult | None:
        """Checks to see if an excel sheet has duplicate column names once the
        names are lowered.

        Some sheets will have column names like ...iraq and ...Iraq. These are
        technically different so they can be loaded ok but sheets should not have
        columns with the same name.

        Args:
            columns (list[str]): excel sheet columns
            sheet_name (str): name of excel sheet

        Returns:
            ValidationResult | None: validation error if duplicates are found.
        """
        duplicate_columns = duplicate_list_items(lower_list_items(columns))
        if duplicate_columns:
            result = ValidationResult(
                rule="Excel Sheet Loading",
                message=self._(
                    "base_excel_loader.check_duplicate_columns",
                    excel_sheet=sheet_name,
                    count=len(duplicate_columns),
                ),
                severity=SeverityLevel.ERROR,
                sheet_name=sheet_name,
                details={"duplicate_columns": unique_list(duplicate_columns)},
            )
            return result

    def _(self, key: str, **kwargs: str | int | float):
        return _(key, **kwargs)


@dataclass(slots=True)
class ExcelLoaderData:
    loaded_sheets: list[DataSheetMap] = field(default_factory=list)
    unloaded_sheets: list[DataSheetMap] = field(default_factory=list)
    unexpected_sheets: list[str] = field(default_factory=list)
    hidden_sheets: list[str] = field(default_factory=list)

    def set_column_map_for_loaded_sheet(self, sheet: str, column_maps: list[DataColumnMap]):
        loaded_sheet = self.get_loaded_sheet(sheet)
        if loaded_sheet is not None:
            loaded_sheet.set_column_map(column_maps)

    def get_loaded_sheet_mapped_names(self) -> list[str]:
        """Gets all the standard names for the loaded excel sheets

        Returns:
            List[str]: List of sheet names.
        """
        return [sheet.schema_sheet_name for sheet in self.loaded_sheets]

    def get_loaded_sheet_excel_names(self) -> list[str]:
        """Gets all the excel names for the loaded excel sheets
        that were mapped to the origianl schema.

        This is related to dynamic model creation process.

        Returns:
            List[str]: List of sheet names.
        """
        return [sheet.data_sheet_name for sheet in self.loaded_sheets if not sheet.auto_loaded]

    def get_unloaded_sheet_mapped_names(self) -> list[str]:
        """Gets all the standard names for the loaded excel sheets

        Returns:
            List[str]: List of sheet names.
        """
        return [sheet.schema_sheet_name for sheet in self.unloaded_sheets]

    def get_loaded_sheet(self, sheet_name: str) -> DataSheetMap | None:
        """Gets the details and data for a loaded sheet if it exists.

        Args:
            sheet_name (str): Excel sheets to be searched for

        Returns:
            SheetMap | None: Loaded sheet details if found
        """
        for sheet in self.loaded_sheets:
            if sheet.schema_sheet_name == sheet_name:
                return sheet
        return None

    def remove_loaded_sheet(self, sheet_name: str):
        for idx, sheet in enumerate(self.loaded_sheets):
            if sheet.schema_sheet_name == sheet_name:
                _ = self.loaded_sheets.pop(idx)

    def get_sheet_matches(self, sheet_name: str) -> list[DataSheetMap]:
        """Gets all the sheets matched with a given schema_name.

        Args:
            sheet_name (str): Excel sheets to be searched for

        Returns:
            List[SheetMap] | None: Loaded sheet details if found
        """
        sheets: list[DataSheetMap] = []
        for sheet in self.loaded_sheets:
            if sheet.schema_sheet_name == sheet_name:
                sheets.append(sheet)

        for sheet in self.unloaded_sheets:
            if sheet.schema_sheet_name == sheet_name:
                sheets.append(sheet)

        return sheets
