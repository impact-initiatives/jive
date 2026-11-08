from argus.validators.common_validators.raw_clean_cleaning_log_validator import (
    RawToCleanToLogCheck,
)
from tests.helpers import (
    build_excel_data,
    build_schema_with_process,
    do_basic_checks,
    error_counter,
)


def get_validator(schema, cleaning_log_sheet: str | None = "cleaning_log"):
    """Create a UniqueColumn validator instance"""
    return RawToCleanToLogCheck(schema=schema, cleaning_log_sheet=cleaning_log_sheet)


class TestRawCleanCleaningLog:
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

    def test_missing_cleaning_log_value(
        self,
    ):
        # diff between raw and clean but uuid has no record in cleaning log
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
                    ("uuid", [1]),
                    ("variable", ["question2"]),
                    ("new_value", ["a"]),
                    ("old_value", ["a"]),
                    ("change_type", ["yes"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results is not None
        assert filtered_results[0].details is not None
        assert filtered_results[0].details["uuid"][0] == 5

    def test_all_cleaning_log_value(
        self,
    ):
        # diff between raw and clean but uuid has no record in cleaning log
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
                    ("uuid", ["1", "2", "3", "4", "5"]),
                    ("question1", [1, 2, 3, 4, 5]),
                    ("question2", ["b", "c", "f", "a", "a"]),
                ],
                "raw_data": [
                    ("uuid", ["1", "2", "3", "4", "5"]),
                    ("question1", [1, 2, 3, 4, 4]),
                    ("question2", ["a", "c", "f", "a", "a"]),
                ],
                "cleaning_log": [
                    ("uuid", ["all", "1"]),
                    ("variable", ["question1", "question2"]),
                    ("new_value", ["", "b"]),
                    ("old_value", ["", "a"]),
                    ("change_type", ["variable_added", "yes"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 0)

    def test_missing_cleaning_log_value_question(
        self,
    ):
        # uuid has record in cleaning log but not for this question
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
        assert filtered_results is not None
        assert filtered_results[0].details is not None
        assert filtered_results[0].details["uuid"][0] == 5

    def test_missing_cleaning_log_value_question_no_cleaning_log(
        self,
    ):
        schema = build_schema_with_process(
            {
                "clean_data": ["uuid"],
                "raw_data": ["uuid"],
                # "cleaning_log": ["uuid", "new_value", "old_value", "variable", "change_type"],
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
                    ("variable", ["question2"]),
                    ("new_value", [""]),
                    ("old_value", [4]),
                    ("change_type", ["change_response"]),
                ],
            }
        )
        validor = get_validator(schema, cleaning_log_sheet=None)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        filtered_results = error_counter(result)
        assert filtered_results is not None
        assert filtered_results[0].details is not None
        assert filtered_results[0].details["uuid"][0] == 5
