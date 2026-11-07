from argus.validators.common_validators.cleaning_log_to_clean_validator import (
    CleaningLogToCleanCheck,
)
from tests.helpers import (
    build_excel_data,
    build_schema_with_process,
    do_basic_checks,
    error_counter,
)


def get_validator(schema, cleaning_log_sheet: str | None = "cleaning_log"):
    """Create a UniqueColumn validator instance"""
    return CleaningLogToCleanCheck(schema=schema, cleaning_log_sheet=cleaning_log_sheet)


class TestCleaningLog:
    def test_valid_data(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
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
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data_missing": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
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
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid_missing", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_schema_sheet(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log_missing": [
                    "uuid",
                    "new_value",
                    "old_value",
                    "variable",
                    "change_type",
                ],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_cleaning_log_column(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value_missing", [4]),
                    ("change_type", ["change_response"]),
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
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation_missing": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_invalid_clean_data(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 7]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["uuid"]) == 1
        assert filtered_results[0].details["variable"][0] == "question1"

    def test_missing_question_clean_data(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question_missing", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question1"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["variable"]) == 1
        assert filtered_results[0].details["variable"][0] == "question1"

    def test_missing_question_cleaning_log(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5]),
                    ("variable", ["question_missing"]),
                    ("new_value", [5]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["variable"]) == 1
        assert filtered_results[0].details["variable"][0] == "question_missing"

    def test_multientry_data(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [5, 5]),
                    ("variable", ["question1", "question1"]),
                    ("new_value", [5, 6]),
                    ("old_value", [4, 4]),
                    ("change_type", ["change_response", "change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["uuid"]) == 2

    def test_empty_value_data(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["4", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [1]),
                    ("variable", ["question2"]),
                    ("new_value", [""]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 0)

    def test_empty_value_data_invalid(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["4", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [1]),
                    ("variable", ["question2"]),
                    ("new_value", [""]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["uuid"]) == 1
        assert filtered_results[0].details["cleaning_log_value"][0] == ""

    def test_same_old_new_value(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
            },
            process_details={
                "cleaning_log_validation": ["yes", "change_response"],
            },
            process_sheet="cleaning_log",
            process_column="change_type",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", [1, 2, 3, 4, 5]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["4", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", [1]),
                    ("variable", ["question2"]),
                    ("new_value", ["a"]),
                    ("old_value", ["a"]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results[0].details is not None
        assert len(filtered_results[0].details["uuid"]) == 1
        assert filtered_results[0].details["old_value"][0] == "a"
