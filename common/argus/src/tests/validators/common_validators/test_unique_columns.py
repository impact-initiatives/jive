from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.unique_column_validator import (
    UniqueColumnCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return UniqueColumnCheck(schema=schema)


def build_schema(sheet_name: str, column: str, unique: bool):

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name=sheet_name,
                columns=[SchemaColumnMap(standard_name=column, is_unique=unique)],
            )
        ],
        unloaded_sheets=[],
    )


class TestUniqueColumns:
    def test_unique_column(
        self,
    ):
        schema = build_schema("clean_data", "uuid", unique=True)
        data = build_excel_data({"clean_data": [("uuid", [1, 2, 3])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_no_unique_columns_schema(
        self,
    ):
        schema = build_schema("clean_data", "uuid", unique=False)
        data = build_excel_data({"clean_data": [("uuid", [1, 1, 3])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_invalid_unique_column_str(
        self,
    ):
        schema = build_schema("clean_data", "uuid", unique=True)
        data = build_excel_data({"clean_data": [("uuid", ["1", "1", "3"])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["column"][0] == "uuid"

    def test_invalid_unique_column_int(
        self,
    ):
        schema = build_schema("clean_data", "uuid", unique=True)
        data = build_excel_data({"clean_data": [("uuid", [1, 1, 3])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["column"][0] == "uuid"
