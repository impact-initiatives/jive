from argus.validators.common_validators.column_name_validator import (
    ColumnNameCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


def get_validator(ignore_sheets: list[str] | None = None):
    """Create a UniqueColumn validator instance"""
    return ColumnNameCheck(ignore_sheets=ignore_sheets)


class TestColumnNames:
    def test_valid_columns(
        self,
    ):

        data = build_excel_data(
            {
                "raw_data": [
                    ("some_column", [1, 2, 3, 4, 5]),
                    ("some.column", [1, 2, 3, 4, 5]),
                    ("somecolumn", [1, 2, 3, 4, 5]),
                ]
            }
        )
        validator = get_validator()
        result = validator.validate(data)

        do_basic_checks(result, 0)

    def test_invalid_column(
        self,
    ):

        data = build_excel_data({"raw_data": [("some@column", [1, 2, 3, 4, 5])]})
        validator = get_validator()
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["columns"][0] == "some@column"

    def test_invalid_column2(
        self,
    ):

        data = build_excel_data({"raw_data": [("some column", [1, 2, 3, 4, 5])]})
        validator = get_validator()
        result = validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert result[0].details["columns"][0] == "some column"

    def test_ignore_sheet(
        self,
    ):

        data = build_excel_data({"raw_data": [("some@column", [1, 2, 3, 4, 5])]})
        validator = get_validator(ignore_sheets=["raw_data"])
        result = validator.validate(data)

        do_basic_checks(result, 0)
