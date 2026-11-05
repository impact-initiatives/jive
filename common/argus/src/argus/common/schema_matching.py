from ..loaders.base import DataColumnMap, DataSheetMap
from ..models.base_dataset_schemas import BaseDatasetSchema


def get_matching_unique_columns(
    schema: BaseDatasetSchema, loaded_data: DataSheetMap, sheet_name: str
) -> list[DataColumnMap]:
    """matches schema unique columns to loaded data column

    Args:
        loaded_data (LoadedSheet): the excel loaded data sheet to match with
        sheet_name (str): the schema sheet to match with

    Returns:
        list[Any] | list[str]: a list of matched columns
    """

    sheet = schema.get_schema_loaded_sheet(sheet_name)
    matching_columns: list[DataColumnMap] = []

    if sheet is not None:
        unique_columns = sheet.get_unique_columns()

        if unique_columns:
            for column in unique_columns:
                column_map = loaded_data.get_column_map(column.standard_name)
                if column_map is not None:
                    matching_columns.append(column_map)

    return matching_columns
