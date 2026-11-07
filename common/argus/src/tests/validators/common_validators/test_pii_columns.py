import pytest

from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.pii_validator import PiiDataCheck
from tests.helpers import build_excel_data, do_basic_checks, error_counter


def get_validator(valid_schema, ignore_sheets: list[str] | None = None):
    """Create a UniqueColumn validator instance"""
    return PiiDataCheck(schema=valid_schema, ignore_sheets=ignore_sheets)


@pytest.fixture
def valid_schema():

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name="raw_data",
                alternate_names=["raw_data"],
                columns=[
                    SchemaColumnMap(
                        standard_name="uuid",
                        alternate_names=["uuidx", "X_uuid", "uuid2"],
                        is_unique=True,
                    )
                ],
            )
        ],
        unloaded_sheets=[],
    )


class TestPiiColumns:
    def test_valid_data(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("uuid", [1, 2, 3, 4, 5])]})
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_invalid_data(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("phone_number", [1, 2, 3, 4, 5])]})
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)

    def test_invalid_fuzzy_data(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("phone_number1", [1, 2, 3, 4, 5])]})
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        do_basic_checks(result, 1)

    def test_email_match(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("some_column", ["a@b.com", "2", "3", "4", "5"])]})
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        filtered_results = error_counter(result)
        do_basic_checks(filtered_results, 1)
        assert filtered_results[0].details is not None
        assert filtered_results[0].details["pii_type"][0] == "email"
        assert filtered_results[0].details["matched_value"][0] == "a@b.com"

    def test_phone_number_match(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("some_column", ["1", "2", "3", "4", "0557456783"])]})
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        filtered_results = error_counter(result)
        do_basic_checks(filtered_results, 1)
        assert filtered_results[0].details is not None
        assert filtered_results[0].details["pii_type"][0] == "phone"
        assert filtered_results[0].details["matched_value"][0] == "0557456783"

    def test_phone_number_too_short(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("some_column", ["1", "2", "3", "4", "01235"])]})
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        filtered_results = error_counter(result)
        do_basic_checks(filtered_results, 0)

    def test_phone_number_match_id_column(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data(
            {
                "raw_data": [
                    ("some_column", ["1", "2", "3", "4", "0557456783"]),
                    ("uuid", ["1", "2", "3", "4", "5"]),
                ]
            }
        )
        validator = get_validator(valid_schema)
        result = validator.validate(data)

        filtered_results = error_counter(result)
        do_basic_checks(filtered_results, 1)
        assert filtered_results[0].details is not None
        assert filtered_results[0].details["pii_type"][0] == "phone"
        assert filtered_results[0].details["matched_value"][0] == "0557456783"

    def test_ignore_sheet(self, valid_schema: BaseDatasetSchema):
        data = build_excel_data({"raw_data": [("phone_number", [1, 2, 3, 4, 5])]})
        validator = get_validator(valid_schema, ignore_sheets=["raw_data"])
        result = validator.validate(data)

        do_basic_checks(result, 0)
