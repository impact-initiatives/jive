import polars as pl

from argus.loaders.base_excel_loader import ExcelLoaderData
from argus.loaders.excel_loader import DataSheetMap
from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.duplicate_sheet_match_validator import (
    DuplicateSheetMatchCheck,
)
from tests.helpers import do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return DuplicateSheetMatchCheck(schema=schema)


def build_schema(sheet_name: str, columns: list[str], matching_term: str | None = None):
    column_map: list[SchemaColumnMap] = []
    for column in columns:
        column_map.append(SchemaColumnMap(standard_name=column))

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name=sheet_name, columns=column_map, matching_term=matching_term
            )
        ],
        unloaded_sheets=[],
    )


def build_excel_data(sheets: list[tuple[str, str]]):
    """Create ExcelLoaderData with matching columns"""
    df = pl.DataFrame(
        {
            "uuid": [1, 2, 3, 4, 5],
        }
    )

    loaded_sheets: list[DataSheetMap] = []
    for item in sheets:
        loaded_sheets.append(
            DataSheetMap(
                schema_sheet_name=item[0],
                data_sheet_name=item[1],
                data=df,
            )
        )

    return ExcelLoaderData(
        loaded_sheets=loaded_sheets,
    )


class TestDuplicateSheets:
    def test_valid_schema(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"])
        data = build_excel_data([("clean_data", "clean_data")])
        validator = get_validator(schema)

        result = validator.validate(data)
        do_basic_checks(result, 0)

    def test_duplicate_sheet_matches(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"])
        data = build_excel_data([("clean_data", "clean_data"), ("clean_data", "clean_data2")])
        validator = get_validator(schema)

        result = validator.validate(data)
        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["sheet"][0] == "clean_data"

    def test_valid_schema_matching_term(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"], matching_term="clean")
        data = build_excel_data([("clean_data", "clean_data"), ("clean_data", "clean_data2")])
        validator = get_validator(schema)

        result = validator.validate(data)
        do_basic_checks(result, 0)
