from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.missing_sheets_validator import (
    MissingSheetsCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return MissingSheetsCheck(schema=schema)


def build_schema(sheet_name: str, columns: list[str], required=True):
    column_map: list[SchemaColumnMap] = []
    for column in columns:
        column_map.append(SchemaColumnMap(standard_name=column))

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(standard_name=sheet_name, columns=column_map, required=required)
        ],
        unloaded_sheets=[],
    )


class TestMissingSheets:
    def test_valid_schema(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"])
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_missing_sheet(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"])
        data = build_excel_data(
            {
                "other_sheet": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["missing_sheets"]) == 1

    def test_optional_sheet(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"], required=False)
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_optional_missing_sheet(
        self,
    ):
        schema = build_schema("clean_data", ["uuid", "country"], required=False)
        data = build_excel_data(
            {
                "other_sheet": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["optional_sheets"]) == 1

    def test_optional_missing_sampling_sheet(
        self,
    ):
        schema = build_schema("sampling_info", ["uuid", "country"], required=False)
        data = build_excel_data(
            {
                "other_sheet": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
