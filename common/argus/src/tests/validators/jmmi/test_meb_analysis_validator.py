import polars as pl
import pytest

from argus.loaders.base_excel_loader import ExcelLoaderData
from argus.loaders.excel_loader import DataSheetMap
from argus.validators.base import BaseValidator
from argus.validators.jmmi_validators.meb_analysis_validator import (
    JMMIMebAnalysisCheck,
)
from tests.helpers import do_basic_checks


@pytest.fixture
def validator():
    """Create a UniqueColumn validator instance"""
    return JMMIMebAnalysisCheck()


def create_loader_data(
    meb_columns: dict[str, list[str | int | float]], clean_data_sheet="clean_data"
):
    meb_df = pl.DataFrame(meb_columns)

    loaded_sheet = [
        DataSheetMap(
            schema_sheet_name=clean_data_sheet,
            data_sheet_name=clean_data_sheet,
            data=meb_df,
        ),
        DataSheetMap(
            schema_sheet_name="meb_analysis",
            data_sheet_name="meb_analysis",
            data=meb_df,
        ),
    ]

    return ExcelLoaderData(loaded_sheets=loaded_sheet)


class TestColumnNames:
    def test_valid_data(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_local_currency": [13],
                "meb_energy_usd_xrate_official": [13],
            }
        )
        results = validator.validate(data)
        do_basic_checks(results, 0)

    def test_not_enough_currency_columns(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_usd_xrate_official": [13],
            }
        )
        results = validator.validate(data)
        do_basic_checks(results, 1)
        assert results[0].details is None

    def test_not_enough_xrate_columns(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_local_currency": [13],
            }
        )
        results = validator.validate(data)
        do_basic_checks(results, 1)
        assert results[0].details is None

    def test_numeric_column_no_suffix(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_local_currency": [13],
                "meb_energy_usd_xrate_official": [13],
                "meb_nfi_usd_xrate": [13],
            }
        )
        results = validator.validate(data)
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert len(results[0].details["numeric columns without suffix"]) == 1

    def test_non_numeric_column_with_suffix(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_local_currency": [13],
                "meb_energy_usd_xrate_official": [13],
                "meb_nfi_usd_xrate_official": ["13"],
            }
        )
        results = validator.validate(data)
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert len(results[0].details["non-numeric column with numeric suffix"]) == 1

    def test_no_suffix_not_numeric(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_local_currency": [13],
                "meb_energy_usd_xrate": ["13"],
                "meb_food_usd_xrate_parallel": ["13"],
            }
        )
        results = validator.validate(data)
        do_basic_checks(results, 2)
        assert results[1].details is not None
        assert len(results[1].details["non-numeric column with numeric suffix"]) == 1

    def test_missing_sheet(self, validator: BaseValidator):
        data = create_loader_data(
            {
                "meb_food_local_currency": [800],
                "meb_food_usd_xrate_official": [10],
                "meb_energy_local_currency": [13],
                "meb_energy_usd_xrate_official": [13],
            },
            clean_data_sheet="missing",
        )
        results = validator.validate(data)
        do_basic_checks(results, 1)
        assert "clean_data" in results[0].message
