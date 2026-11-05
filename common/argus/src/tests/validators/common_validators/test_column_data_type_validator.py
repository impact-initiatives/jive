from argus.validators.common_validators.column_data_type_validator import (
    DataTypeCheck,
)
from tests.helpers import build_excel_data, build_schema_with_process, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return DataTypeCheck(schema=schema)


class TestDataType:
    def test_valid_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 0)

    def test_missing_data_sheet(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data_missing": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_schema_clean_sheet(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data_missing": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_schema_survey_sheet(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey_missing": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_data_column(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type_missing", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_schema_column(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name_missing"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_process(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_process_values(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": [],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_invalid_date(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", [1, 2, 3]),
                    ("question2", [1.5, 26.6, 3.7]),
                    ("question3", ["not a date", "56412314", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2

    def test_invalid_numeric(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", ["1", "not a number", "3"]),
                    ("question2", ["1.5", "26.6", "not a number"]),
                    ("question3", ["2026-01-01", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2

    def test_invalid_date_and_numeric(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question1", ["1", "not a number", "3"]),
                    ("question2", ["1.5", "26.6", "not a number"]),
                    ("question3", ["not a date", "2026-01-01", "2026-01-01"]),
                    ("other", ["qwe", "wer", "qtr"]),
                ],
                "survey": [
                    ("type", ["integer", "decimal", "date"]),
                    ("name", ["question1", "question2", "question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 2)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 2
        assert result[1].details is not None
        assert len(result[1].details["uuid"]) == 1

    def test_date_as_numeric(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"]},
            process_details={
                "data_type_numeric_check": ["integer", "decimal"],
                "data_type_temporal_check": ["date"],
            },
            process_sheet="survey",
            process_column="type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("question3", [31231, 45456, 789789]),
                ],
                "survey": [
                    ("type", ["date"]),
                    ("name", ["question3"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 3
        assert "non-temporal values" in result[0].message
