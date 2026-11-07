from pathlib import Path

import pytest

from argus.validators.base import BaseValidator
from argus.validators.jmmi_validators.column_data_validator import (
    JMMIColumnDataCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


@pytest.fixture
def validator():
    """Create a UniqueColumn validator instance"""
    return JMMIColumnDataCheck()


class TestColumnData:
    def test_valid_data(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 0)

    def test_missing_country(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", [""]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert "should be 3 uppercase" in results[0].details["issue"][0]

    def test_invalid_country(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SD"]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert "should be 3 uppercase" in results[0].details["issue"][0]

    def test_round_invalid_country(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    ("round", ["SD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert "start with 'country'" in results[0].details["issue"][0]

    def test_round_invalid_month(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["April"]),
                    ("year", ["2026"]),
                    ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert "start with 'country'" in results[0].details["issue"][0]

    def test_round_invalid_year(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["March"]),
                    ("year", ["2025"]),
                    ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is not None
        assert "start with 'country'" in results[0].details["issue"][0]

    def test_missing_country_column(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    # ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is None
        assert "country" in results[0].message

    def test_missing_round_column(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    # ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is None
        assert "round" in results[0].message

    def test_missing_sheet(self, validator: BaseValidator):
        data = build_excel_data(
            {
                "clean_data_missing": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                    ("month", ["March"]),
                    ("year", ["2026"]),
                    # ("round", ["SSD_JMMI_March_2026"]),
                ],
                "meb_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
                "mfs_analysis": [
                    ("admin1_code", ["admincode"]),
                    ("country", ["SSD"]),
                ],
            }
        )
        results = validator.validate(data, dataset_config_directory=Path("./some/location"))
        do_basic_checks(results, 1)
        assert results[0].details is None
        assert "clean_data" in results[0].message
