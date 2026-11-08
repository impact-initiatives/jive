from dataclasses import dataclass, field
from enum import StrEnum, auto

import polars as pl
from pydantic import BaseModel, Field, model_validator

from ..common.list_matching import add_to_list, unique_list


class SheetClassification(StrEnum):
    CLEAN_DATA_SHEET = auto()
    RAW_DATA_SHEET = auto()
    CLEANING_LOG_SHEET = auto()
    DELETION_LOG_SHEET = auto()
    OTHER = auto()
    UNKNOWN = auto()


@dataclass(slots=True)
class DynamicSheetMatching:
    """
    parent_sheet, parent_linking_column for linking:
        - deletion log to raw
        - cleaning log to clean
        - repeat group to parent
    linked_sheet for linking:
        - raw and clean sheets
    linked_log for linking:
        - raw to deletion log
        - clean to cleaning log
    """

    data: pl.DataFrame
    base_sheet_name: str
    id_column: str | None
    id_column_set: set[str | int | float] | None
    classification: SheetClassification = SheetClassification.UNKNOWN
    parent_sheet: str | None = None
    parent_linking_column: str | None = None
    children: list[str] = field(default_factory=list)
    linked_log: str | None = None
    linked_sheet: str | None = None
    log_id_column: list[str] = field(default_factory=list)


class ProcessValueMap(BaseModel):
    """Values expected in a column required for a validation process"""

    process_name: str
    values: list[str | int | float] = Field(default=[])

    @model_validator(mode="after")
    def lowercase_all(self):
        self.process_name = self.process_name.lower()
        self.values = [item.lower() if isinstance(item, str) else item for item in self.values]
        return self


class SchemaColumnMap(BaseModel):
    standard_name: str
    alternate_names: list[str] = Field(default=[])
    is_unique: bool = False
    process_values: list[ProcessValueMap] = Field(default=[])
    allow_fuzzy_matching: bool = True
    required: bool = True
    allow_empty_values: bool = True

    @model_validator(mode="after")
    def lowercase_all(self):
        self.standard_name = self.standard_name.lower()
        self.alternate_names = [name.lower() for name in self.alternate_names]
        return self

    def combine(self) -> list[str]:
        """returns a unique list of column names and alternate names"""
        return add_to_list(self.standard_name, self.alternate_names)

    def get_process_values(self, process_name: str):
        for item in self.process_values:
            if item.process_name == process_name:
                return item


class SchemaSheetMap(BaseModel):
    """
    parent_sheet, parent_linking_column for linking:
        - deletion log to raw
        - cleaning log to clean
        - repeat group to parent
    linked_sheet for linking:
        - raw and clean sheets
    linked_log for linking:
        - raw to deletion log
        - clean to cleaning log
    """

    standard_name: str
    classification: SheetClassification = SheetClassification.OTHER
    alternate_names: list[str] = Field(default=[])
    columns: list[SchemaColumnMap] = Field(default=[])
    allow_fuzzy_matching: bool = True
    required: bool = True
    # if setting a matching term, the fuzzy matching config will be ignored
    matching_term: str | None = None
    matching_term_ignore: list[str] = Field(default=[])
    # these are used to build some validaton rules and support sheet id linking
    parent_sheet: str | None = None
    parent_linking_column: str | None = None
    linked_sheet: str | None = None
    linked_log: str | None = None

    @model_validator(mode="after")
    def lowercase_all(self):
        self.standard_name = self.standard_name.lower()
        self.alternate_names = [name.lower() for name in self.alternate_names]
        self.matching_term = self.matching_term.lower() if self.matching_term is not None else None
        self.matching_term_ignore = [name.lower() for name in self.matching_term_ignore]
        return self

    def get_column(self, column_name: str) -> SchemaColumnMap | None:
        """Returns a column from columns if a name is matched."""
        for column in self.columns:
            if column.standard_name == column_name:
                return column

    def get_column_standard_names(self):
        """Gets the standard names for all mandatory columns."""
        return [item.standard_name for item in self.columns]

    def get_unique_columns(self) -> list[SchemaColumnMap]:
        """Gets all the columns markes as unique"""
        return [column for column in self.columns if column.is_unique]

    def get_not_empty_columns(self) -> list[SchemaColumnMap]:
        """Gets all the columns markes as unique"""
        return [column for column in self.columns if not column.allow_empty_values]

    def combine_column_names(self, return_unique_list: bool = True) -> list[str]:
        """Creates a unique list of mandatory and unique column name options

        Args:
            include_unique_columns (bool, optional): Include unique columns in
              the results. Defaults to True.
            return_unique_list (bool, optional): return a list of unique values.
              Defaults to True.

        Returns:
            List[str]: returns a list of column names and alternate names for a sheet
        """
        column_list: list[str] = []
        for column in self.columns:
            column_list.extend(column.combine())

        # this list may have dupliaces if columns share names or laternate names
        if return_unique_list:
            return unique_list(column_list)
        else:
            return column_list

    def combine_sheet_names(self) -> list[str]:
        """combines standard_name and alternate_names into one list checking
        standard_name is not in alternate_names list

        Returns:
            List[str]: combined list of unique items
        """
        return add_to_list(self.standard_name, self.alternate_names)

    def add_column(self, column: SchemaColumnMap) -> SchemaColumnMap | None:
        """Adds a column to columns if the standard_name provided
        does not exist.

        If the name exists within alternate_names then the schema prevalidation
        process will detect it and report an error.

        Returns None if a column with the same standard_name already exists

        Returns:
            ColumnMapping | None: the new column or None
        """

        if self.get_column(column.standard_name) is None:
            self.columns.append(column)
            return column
