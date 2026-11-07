import polars as pl
import pytest

from argus.loaders.base_excel_loader import ExcelLoaderData
from argus.loaders.excel_loader import DataSheetMap
from argus.validators.base import BaseValidator
from argus.validators.common_validators.unexpected_sheets_validator import (
    UnexpectedSheetsCheck,
)
from tests.helpers import do_basic_checks


@pytest.fixture
def get_validator():
    """Create a UniqueColumn validator instance"""
    return UnexpectedSheetsCheck()


def build_excel_data(sheet_name: str, unexpected_sheets: list[str], hidden_sheets: list[str]):
    """Create ExcelLoaderData with matching columns"""
    df = pl.DataFrame(
        {
            "uuid": [1, 2, 3, 4, 5],
        }
    )

    loaded_sheet = DataSheetMap(
        schema_sheet_name=sheet_name,
        data_sheet_name=sheet_name,
        data=df,
    )

    return ExcelLoaderData(
        loaded_sheets=[loaded_sheet],
        unexpected_sheets=unexpected_sheets,
        hidden_sheets=hidden_sheets,
    )


class TestUnexpectedSheets:
    def test_unexpected_sheets(
        self,
        get_validator: BaseValidator,
    ):
        data = build_excel_data(
            sheet_name="clean_data",
            unexpected_sheets=["somesheet", "anothersheet"],
            hidden_sheets=[],
        )
        result = get_validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["unexpected_sheets"]) == 2

    def test_hidden_sheet(
        self,
        get_validator: BaseValidator,
    ):
        data = build_excel_data(
            sheet_name="clean_data",
            unexpected_sheets=[],
            hidden_sheets=["somesheet", "anothersheet"],
        )
        result = get_validator.validate(data)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["hidden_sheets"]) == 2

    def test_expected_sheets(
        self,
        get_validator: BaseValidator,
    ):
        data = build_excel_data(sheet_name="clean_data", unexpected_sheets=[], hidden_sheets=[])
        result = get_validator.validate(data)

        do_basic_checks(result, 0)
