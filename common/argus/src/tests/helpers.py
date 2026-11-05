import polars as pl

from argus.loaders.base import DataColumnMap, DataSheetMap
from argus.loaders.base_excel_loader import ExcelLoaderData
from argus.models.base import ProcessValueMap, SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.base import SeverityLevel, ValidationResult


def error_counter(results: list[ValidationResult]):
    """Filter out some results to get a list of errors/warnings only."""
    return [
        item
        for item in results
        if item.severity in [SeverityLevel.ERROR, SeverityLevel.ADMIN_ERROR, SeverityLevel.WARNING]
    ]


def admin_error_counter(results: list[ValidationResult]):
    """Filter out some results to get a list of admin errors only."""
    return [item for item in results if item.severity == SeverityLevel.ADMIN_ERROR]


def do_basic_checks(results: list[ValidationResult], expected: int):
    assert isinstance(results, list)
    assert len(error_counter(results)) == expected


def build_excel_data(sheet_details: dict[str, list[tuple[str, list[str | int | float | None]]]]):
    """Create ExcelLoaderData with matching columns"""
    loaded_sheets: list[DataSheetMap] = []
    for sheet, columns in sheet_details.items():
        column_map: list[DataColumnMap] = []
        columns_dict = {}

        for column in columns:
            column_map.append(
                DataColumnMap(schema_column_name=column[0], data_column_name=column[0])
            )
            columns_dict[column[0]] = column[1]

        df = pl.DataFrame(columns_dict)

        loaded_sheets.append(
            DataSheetMap(
                schema_sheet_name=sheet,
                data_sheet_name=sheet,
                data=df,
                column_map=column_map,
            )
        )

    return ExcelLoaderData(
        loaded_sheets=loaded_sheets,
    )


def build_schema_with_attributes(sheet_details: dict[str, dict[str, str]]):
    sheet_maps: list[SchemaSheetMap] = []
    for sheet, attributes in sheet_details.items():
        new_sheet = SchemaSheetMap(standard_name=sheet)
        for key, value in attributes.items():
            setattr(new_sheet, key, value)
        sheet_maps.append(new_sheet)

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=sheet_maps,
        unloaded_sheets=[],
    )


def build_schema_with_process(
    sheet_details: dict[str, list[str]],
    process_details: dict[str, list[str | int | float]],
    process_sheet: str,
    process_column: str,
    unique_columns: bool = True,
):
    sheet_maps: list[SchemaSheetMap] = []

    for sheet, columns in sheet_details.items():
        column_map: list[SchemaColumnMap] = []

        for column in columns:
            if sheet == process_sheet and column == process_column:
                process_values_map: list[ProcessValueMap] = []
                for process_name, proces_values in process_details.items():
                    process_values_local = proces_values.copy()
                    if process_values_local is None:
                        process_values_local = []

                    if process_name is not None:
                        process_values_map.append(
                            ProcessValueMap(process_name=process_name, values=process_values_local)
                        )

                column_map.append(
                    SchemaColumnMap(standard_name=column, process_values=process_values_map)
                )
            else:
                column_map.append(SchemaColumnMap(standard_name=column, is_unique=unique_columns))

        sheet_maps.append(SchemaSheetMap(standard_name=sheet, columns=column_map))

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=sheet_maps,
        unloaded_sheets=[],
    )
