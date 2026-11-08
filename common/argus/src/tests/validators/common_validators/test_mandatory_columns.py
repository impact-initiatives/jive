from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.mandatory_column_validator import (
    MandatoryColumnsCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return MandatoryColumnsCheck(schema=schema)


def build_schema(sheet_name: str, columns: list[tuple[str, bool]], required=True):
    column_map: list[SchemaColumnMap] = []
    for column in columns:
        column_map.append(SchemaColumnMap(standard_name=column[0], required=column[1]))

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(standard_name=sheet_name, columns=column_map, required=required)
        ],
        unloaded_sheets=[],
    )


class TestMandatoryColumns:
    def test_valid_schema(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", True)])
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("country", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_no_mandatory_columns(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", False), ("country", False)])
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("country", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_missing_required_column(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", True)])
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["required"]) == 1
        assert result[0].details["required"][0] == "Yes"

    def test_multiple_missing_required_column(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", True), ("admin_1", True)])
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["required"]) == 2
        assert result[0].details["required"][0] == "Yes"

    def test_missing_required_column_optional_sheet(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", True)], required=False)
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["required"]) == 1
        assert result[0].details["required"][0] == "Yes"

    def test_missing_optional_column(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", False)])
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["required"]) == 1
        assert result[0].details["required"][0] == "Check if required"

    def test_missing_optional_column_optional_sheet(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", False)], required=False)
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["required"]) == 1
        assert result[0].details["required"][0] == "Check if required"

    def test_missing_sheet(
        self,
    ):
        schema = build_schema("clean_data", [("uuid", True), ("country", True)])
        data = build_excel_data(
            {
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator(schema)

        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["missing_sheets"]) == 1
