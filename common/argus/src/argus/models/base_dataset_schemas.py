import itertools

from pydantic import BaseModel, Field

from argus.models.base import SchemaColumnMap, SchemaSheetMap


class BaseDatasetSchema(BaseModel):
    programme_type: str
    output_type: str
    # sheets that have to be loaded and used for further validation
    loaded_sheets: list[SchemaSheetMap] = Field(default=[])
    # sheets that should exist but dont need to be loaded
    unloaded_sheets: list[SchemaSheetMap] = Field(default=[])

    def get_schema_loaded_sheet(self, sheet_name: str) -> SchemaSheetMap | None:
        """Gets the details and data for a loaded sheet if it exists.

        Args:
            sheet_name (str): Schema sheets to be searched for

        Returns:
            LoadedSheet | None: Loaded sheet details if found
        """
        for sheet in self.loaded_sheets:
            if sheet.standard_name == sheet_name:
                return sheet
        return None

    def get_schema_sheet(self, sheet_name: str):
        """searches both loaded and unloaded sheets for the provided
        sheet name.

        Args:
            sheet_name (str): Schema sheets to be searched for

        Returns:
            LoadedSheet | None: Loaded sheet details if found
        """
        sheet = self.get_schema_loaded_sheet(sheet_name)
        if sheet is None:
            sheet = self.get_schema_unloaded_sheet(sheet_name)
        return sheet

    def get_loaded_sheets_standard_names(self, required: bool | None = None) -> list[str]:
        """Gets all the standard names for all the loaded sheets.

        Args:
            required (bool): Determines which sheets to return.
                True: only required sheets
                False: only optional sheets
                None: all sheets
        """
        return [
            item.standard_name
            for item in self.loaded_sheets
            if (item.required == required) or required is None
        ]

    def get_all_sheet_names(self) -> list[str]:
        """Gets all sheet names, including alternate names

        Returns:
            List[List[str]]: list of all sheet names
        """
        sheet_names = [item.combine_sheet_names() for item in self.loaded_sheets]
        sheet_names.extend([item.combine_sheet_names() for item in self.unloaded_sheets])

        return list(itertools.chain.from_iterable(sheet_names))

    def get_sheet_column_standard_names(self, sheet_name: str) -> list[str] | None:
        """gets all the column standard names for a sheet."""
        sheet = self.get_schema_loaded_sheet(sheet_name)
        if sheet is not None:
            return sheet.get_column_standard_names()

    def get_schema_unloaded_sheet(self, sheet_name: str) -> SchemaSheetMap | None:
        """Gets the details and data for an unloaded sheet if it exists.

        Args:
            sheet_name (str): Schema sheets to be searched for

        Returns:
            LoadedSheet | None: Loaded sheet details if found
        """
        for sheet in self.unloaded_sheets:
            if sheet.standard_name == sheet_name:
                return sheet
        return None

    def add_loaded_sheet(self, sheet: SchemaSheetMap) -> SchemaSheetMap:
        """Adds a sheet to schema_loaded_sheets if the standard_name provided
        does not exist.

        If the name exists within alternate_names then the schema prevalidation
        process will detect it and report an error.

        Returns None if a sheet with the same standard_name already exists


        Args:
            sheet (SheetMapping): sheet to be added

         Returns:
            SheetMapping | None: the new sheet or None
        """

        loaded_sheet = self.get_schema_loaded_sheet(sheet.standard_name)
        if loaded_sheet is None:
            self.loaded_sheets.append(sheet)
        return sheet

    def add_unloaded_sheet(self, sheet: SchemaSheetMap) -> SchemaSheetMap | None:
        """Adds a sheet to schema_unloaded_sheets if the standard_name provided
        does not exist.

        If the name exists within alternate_names then the schema prevalidation
        process will detect it and report an error.

        Returns None if a sheet with the same standard_name already exists

        Args:
            sheet (SheetMapping): sheet to be added

         Returns:
            SheetMapping | None: the new sheet or None

        """
        if self.get_schema_unloaded_sheet(sheet.standard_name) is None:
            self.unloaded_sheets.append(sheet)
            return sheet

    def add_column_to_sheet(
        self, sheet_standard_name: str, column: SchemaColumnMap
    ) -> SchemaSheetMap | None:
        """Adds a mandatory column to an existing sheet.
           If:
            - the sheet does not exist
            - the column already exists (based on standard_name)
            then None will be returned


        Args:
            sheet_standard_name (str): sheet where column is to be added
            column (ColumnMapping): column to be added

        Returns:
            SheetMapping | None: the sheet with the new column added or None
        """
        sheet = self.get_schema_loaded_sheet(sheet_standard_name)
        if sheet is not None:
            _ = sheet.add_column(column)
            return sheet

    def remove_loaded_sheet(self, sheet_standard_name: str):
        """Removes a loaded sheet based on its standard name.
        Assumes no duplicates as only the first match found is removed.

        Args:
            sheet_standard_name (str): name of sheet to remove
        """
        for index, sheet in enumerate(self.loaded_sheets):
            if sheet.standard_name == sheet_standard_name:
                self.loaded_sheets.pop(index)
                return True

        return False
