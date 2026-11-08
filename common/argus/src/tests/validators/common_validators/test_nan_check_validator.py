from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.nan_check_validator import NaNDataCheck
from tests.helpers import build_excel_data, do_basic_checks, error_counter


def get_validator(schema, sheets: list[str]):
    """Create a UniqueColumn validator instance"""
    return NaNDataCheck(schema=schema, check_sheets=sheets)


def build_schema(sheet_name: str, columns: list[tuple[str, bool]]):
    column_map: list[SchemaColumnMap] = []
    for column in columns:
        column_map.append(SchemaColumnMap(standard_name=column[0], is_unique=column[1]))

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[SchemaSheetMap(standard_name=sheet_name, columns=column_map)],
        unloaded_sheets=[],
    )


class TestNaNDataCheck:
    def test_valid_data(
        self,
    ):
        data = build_excel_data(
            {
                "raw_data": [
                    ("uuid", [1, 2, 3]),
                    ("some_column", [12, 234, 13]),
                    ("some_column", ["tyui", "ghjk", "vnbm"]),
                ]
            }
        )
        schema = build_schema("raw_data", [("uuid", True)])
        validator = get_validator(schema, sheets=["raw_data"])
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_invalid_int_data(
        self,
    ):
        data = build_excel_data({"raw_data": [("uuid", [1, 2, 3]), ("some_column", [12, 999, 13])]})
        schema = build_schema("raw_data", [("uuid", True)])
        validator = get_validator(schema, sheets=["raw_data"])
        result = validator.validate(data)
        filtered_results = error_counter(result)
        do_basic_checks(filtered_results, 1)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["uuid"]) == 1

    def test_invalid_string_data(
        self,
    ):
        data = build_excel_data(
            {"raw_data": [("uuid", [1, 2, 3]), ("some_column", ["12", "999", "13"])]}
        )
        schema = build_schema("raw_data", [("uuid", True)])
        validator = get_validator(schema, sheets=["raw_data"])
        result = validator.validate(data)

        filtered_results = error_counter(result)
        do_basic_checks(filtered_results, 1)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["uuid"]) == 1

    def test_no_id_column(
        self,
    ):
        data = build_excel_data(
            {
                "raw_data": [
                    ("thing", [1, 2, 3]),
                    ("some_column", [12, 234, 13]),
                    ("some_column", ["tyui", "ghjk", "vnbm"]),
                ]
            }
        )
        schema = build_schema("raw_data", [("thing", False)])
        validator = get_validator(schema, sheets=["raw_data"])
        result = validator.validate(data)

        do_basic_checks(result, 1)

    def test_missing_sheet(
        self,
    ):
        data = build_excel_data(
            {
                "raw_data": [
                    ("thing", [1, 2, 3]),
                    ("some_column", [12, 234, 13]),
                    ("some_column", ["tyui", "ghjk", "vnbm"]),
                ]
            }
        )
        schema = build_schema("raw_data", [("thing", False)])
        validator = get_validator(schema, sheets=["raw_data", "missing_sheet"])
        result = validator.validate(data)

        do_basic_checks(result, 1)
