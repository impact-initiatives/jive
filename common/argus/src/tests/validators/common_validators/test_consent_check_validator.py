from argus.models.base import ProcessValueMap, SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.consent_check_validator import (
    ConsentCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return ConsentCheck(schema=schema)


def build_schema(
    sheet_details: dict[str, list[str]],
    process_name: str | None = None,
    process_values: list[str | int | float] | None = None,
    unique_columns: bool = True,
):
    sheet_maps: list[SchemaSheetMap] = []

    if process_values is None:
        process_values = []

    for sheet, columns in sheet_details.items():
        column_map: list[SchemaColumnMap] = []

        for column in columns:
            if sheet == "raw_data" and column == "consent":
                if process_name is not None:
                    process = [ProcessValueMap(process_name=process_name, values=process_values)]
                else:
                    process = []
                column_map.append(SchemaColumnMap(standard_name=column, process_values=process))
            else:
                column_map.append(SchemaColumnMap(standard_name=column, is_unique=unique_columns))

        sheet_maps.append(SchemaSheetMap(standard_name=sheet, columns=column_map))

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=sheet_maps,
        unloaded_sheets=[],
    )


class TestConsentCheck:
    def test_valid_data(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 0)

    def test_consent_not_removed(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1

    def test_missing_data_sheet(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data_missing": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_clean_schema_sheet(
        self,
    ):
        schema = build_schema(
            {"clean_data_missing": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_raw_schema_sheet(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data_missing": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_consent_values(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=[],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_consent_process(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name=None,
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_no_id_columns(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
            unique_columns=False,
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 2)

    def test_no_consent_column_schema(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent_missing"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3])],
                "raw_data": [("uuid", [1, 2, 3, 4]), ("consent", ["yes", "yes", "yes", "no"])],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_no_consent_column_data(
        self,
    ):
        schema = build_schema(
            {"clean_data": ["uuid"], "raw_data": ["uuid", "consent"]},
            process_name="consent_check_validation",
            process_values=["yes"],
        )
        data = build_excel_data(
            {
                "clean_data": [("uuid", [1, 2, 3])],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4]),
                    ("consent_missing", ["yes", "yes", "yes", "no"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
