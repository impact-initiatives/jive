from argus.validators.common_validators.survey_choices_validator import (
    SurveyChoicesCheck,
)
from tests.helpers import build_excel_data, build_schema_with_process, do_basic_checks


def get_validator(schema):
    """Create a UniqueColumn validator instance"""
    return SurveyChoicesCheck(schema=schema)


class TestSurveyChoices:
    def test_valid_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 0)

    def test_missing_sheet_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey_missing": [
                    ("type", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_column_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type_missing", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_missing_id_column(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
            unique_columns=False,
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)

    def test_invalid_select_one_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["invalid_gender", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "invalid_gender"

    def test_invalid_select_multiple_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice apples", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["0", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "rice apples"

    def test_invalid_choice_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice flour", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["0", "1", "0"]),
                    ("items.flour", ["1", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    (
                        "name",
                        ["male man", "female", "other", "rice", "pasta", "flour", "super_food"],
                    ),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "male"

    def test_missing_choices_selectone_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender_missing", "select_multiple item", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["value"]) == 1
        assert result[0].details["value"][0] == "gender_missing"

    def test_missing_choices_selectmultiple_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("gender", ["male", "female", "other"]),
                    ("items", ["rice pasta", "pasta super_food", "flour"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["1", "1", "0"]),
                    ("items.flour", ["0", "0", "1"]),
                    ("items.super_food", ["0", "1", "0"]),
                    (
                        "question3",
                        [
                            1,
                            2,
                            3,
                        ],
                    ),
                ],
                "survey": [
                    ("type", ["select_one gender", "select_multiple item_missing", "integer"]),
                    ("name", ["gender", "items", "question3"]),
                ],
                "choices": [
                    ("list_name", ["gender", "gender", "gender", "item", "item", "item", "item"]),
                    ("name", ["male", "female", "other", "rice", "pasta", "flour", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["value"]) == 1
        assert result[0].details["value"][0] == "item_missing"


class TestSurveyBinaryChoices:
    def test_valid_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", "none"]),
                    ("items.rice", [1, 0, 0]),
                    ("items.pasta", [1, 1, 0]),
                    ("items.none", ["0", "0", "1"]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 0)

    def test_invalid_binary_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", ""]),
                    ("items.rice", ["1", "0", ""]),
                    ("items.pasta", ["3", "1", ""]),
                    ("items.none", ["0", "0", ""]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "3"

    def test_empty_binary_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", "none"]),
                    ("items.rice", [1, 0, 0]),
                    ("items.pasta", ["", "1", "0"]),
                    ("items.none", ["0", "0", "1"]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == ""

    def test_empty_binary_data_2(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", ""]),
                    ("items.rice", ["1", "0", ""]),
                    ("items.pasta", ["1", "1", ""]),
                    ("items.none", ["0", "0", "1"]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["uuid"][0] == "3"
        assert result[0].details["value"][0] == "1"

    def test_empty_binary_data_3(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", ""]),
                    ("items.rice", ["1", "0", ""]),
                    ("items.pasta", ["1", "1", ""]),
                    ("items.none", ["", "0", ""]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == ""
        assert result[0].details["uuid"][0] == "1"

    def test_binary_not_in_parent_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice", "pasta", ""]),
                    ("items.rice", ["1", "0", ""]),
                    ("items.pasta", ["1", "1", ""]),
                    ("items.none", ["0", "0", ""]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "1"
        assert result[0].details["uuid"][0] == "1"

    def test_binary_not_in_parent_data_2(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice", "pasta", ""]),
                    ("items.rice", ["1", "0", ""]),
                    ("items.pasta", ["0", "1", ""]),
                    ("items.super_food", ["0", "0", "1"]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "super_food"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "1"
        assert result[0].details["uuid"][0] == "3"

    def test_parent_not_in_binary_data(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", "none"]),
                    ("items.rice", ["1", "0", "0"]),
                    ("items.pasta", ["0", "1", "0"]),
                    ("items.none", ["0", "0", "1"]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["uuid"]) == 1
        assert result[0].details["value"][0] == "0"
        assert result[0].details["uuid"][0] == "1"

    def test_missing_binary_column(
        self,
    ):
        schema = build_schema_with_process(
            {"clean_data": ["uuid"], "survey": ["type", "name"], "choices": ["list_name", "name"]},
            process_details={},
            process_sheet="",
            process_column="",
        )
        data = build_excel_data(
            {
                "clean_data": [
                    ("uuid", [1, 2, 3]),
                    ("items", ["rice pasta", "pasta", "none"]),
                    ("items.rice", [1, 0, 0]),
                    ("items.pasta", [1, 1, 0]),
                ],
                "survey": [
                    ("type", ["select_multiple item"]),
                    ("name", ["items"]),
                ],
                "choices": [
                    ("list_name", ["item", "item", "item"]),
                    ("name", ["rice", "pasta", "none"]),
                ],
            }
        )
        validor = get_validator(schema)
        result = validor.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["value"]) == 1
        assert result[0].details["value"][0] == "items.none"
