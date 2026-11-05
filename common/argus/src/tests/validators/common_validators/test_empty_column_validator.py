from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.empty_column_validator import (
    EmptyColumnCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return EmptyColumnCheck(schema=schema)


def build_schema(sheet_name: str, column: str, allow_empty: bool):

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name=sheet_name,
                columns=[SchemaColumnMap(standard_name=column, allow_empty_values=allow_empty)],
            )
        ],
        unloaded_sheets=[],
    )


class TestEmptyColumns:
    def test_valid_data(
        self,
    ):
        schema = build_schema("clean_data", "uuid", allow_empty=False)
        data = build_excel_data({"clean_data": [("uuid", [1, 2, 3])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_missing_data_null(
        self,
    ):
        schema = build_schema("clean_data", "uuid", allow_empty=False)
        data = build_excel_data({"clean_data": [("uuid", [1, None, 3])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["empty_values"][0] == 1

    def test_missing_data_string(
        self,
    ):
        schema = build_schema("clean_data", "uuid", allow_empty=False)
        data = build_excel_data({"clean_data": [("uuid", ["A", "", "C"])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["empty_values"][0] == 1

    def test_missing_data_multiple(
        self,
    ):
        schema = build_schema("clean_data", "uuid", allow_empty=False)
        data = build_excel_data({"clean_data": [("uuid", ["A", "", None])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["empty_values"][0] == 2

    def test_missing_data_allowed(
        self,
    ):
        schema = build_schema("clean_data", "uuid", allow_empty=True)
        data = build_excel_data({"clean_data": [("uuid", [1, None, 3])]})
        validator = get_validator(schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)
