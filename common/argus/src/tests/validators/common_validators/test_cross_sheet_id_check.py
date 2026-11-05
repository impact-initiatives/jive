from collections.abc import Callable

import pytest

from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.common_validators.cross_sheet_id_check_validator import (
    CrossSheetIdCheck,
)
from tests.helpers import build_excel_data, do_basic_checks, error_counter


@pytest.fixture
def valid_schema_validator(
    valid_schema, valid_master_sheet="raw_data", valid_child_sheets=None, valid_is_in=True
) -> Callable[..., CrossSheetIdCheck]:
    """Create a UniqueColumn validator instance"""

    def make_validator(master_sheet=None, child_sheets=None, is_in=None):
        return CrossSheetIdCheck(
            schema=valid_schema,
            master_sheet=master_sheet or valid_master_sheet,
            child_sheets=child_sheets or valid_child_sheets,
            is_in=is_in if is_in is not None else valid_is_in,
        )

    return make_validator


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
                        alternate_names=["uuid", "X_uuid"],
                        is_unique=True,
                    )
                ],
            ),
            SchemaSheetMap(
                standard_name="clean_data",
                alternate_names=["clean_data"],
                columns=[
                    SchemaColumnMap(
                        standard_name="uuid",
                        alternate_names=["uuidx", "X_uuid"],
                        is_unique=True,
                    )
                ],
            ),
            SchemaSheetMap(
                standard_name="deletion_log",
                alternate_names=["deletion_log"],
                columns=[
                    SchemaColumnMap(
                        standard_name="uuid",
                        alternate_names=["uuid", "X_uuid"],
                        is_unique=True,
                    )
                ],
            ),
            SchemaSheetMap(
                standard_name="cleaning_log",
                alternate_names=["cleaning_log"],
                columns=[
                    SchemaColumnMap(
                        standard_name="uuid",
                        alternate_names=["uuid", "X_uuid"],
                        is_unique=True,
                    )
                ],
            ),
        ],
        unloaded_sheets=[],
    )


class TestCrossSheetIdCheck:
    def test_valid_data(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data": [("uuid", [2, 3, 4, 5])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 0)

    def test_empty_sheet(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data": [("uuid", [1, 2, 3, 4, 5])],
                "deletion_log": [("uuid", [])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 0)

    def test_invalid_id(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])],
                "clean_data": [("uuid", [2, 3, 4, 5, 6, 7, 8, 9, 10, 90])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 1)
        filterd_results = error_counter(result)
        assert filterd_results[0].details is not None
        assert filterd_results[0].details["uuid"][0] == "90"

    def test_master_extra_id_column(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5]), ("uuidx", [1, 2, 3, 4, 5])],
                "clean_data": [("uuid", [2, 3, 4, 5])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 0)

    def test_child_extra_id_column(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data": [("uuid", [2, 3, 4, 5]), ("uuidx", [2, 3, 4, 5])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 0)

    def test_child_missing_sheets(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data_missing": [("uuid", [2, 3, 4, 5])],
                "deletion_log_missing": [("uuid", [1])],
                "cleaning_log_missing": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 3)

    def test_master_missing_sheets(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data_missing": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data": [("uuid", [2, 3, 4, 5])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 1)

    def test_master_missing_id_column(
        self, valid_schema_validator: Callable[..., CrossSheetIdCheck]
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid_no_match", [21, 22, 23, 24, 25, 26, 27, 28, 29, 210, 211])],
                "clean_data": [("uuid", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 1)

    def test_deletion_log_missing_id_column(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5, 6, 7, 8, 9])],
                "clean_data": [("uuid", [2, 3, 4, 5, 6, 7, 8, 9])],
                "deletion_log": [("uuid_no_match", [100])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 1)

    def test_valid_data_ignore_all(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data": [("uuid", [2, 3, 4, 5])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [
                    ("uuid", ["all"]),
                    ("uuid", ["1"]),
                    ("uuid", ["1"]),
                    ("uuid", ["1"]),
                    ("uuid", ["2"]),
                ],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 0)

    def test_invalid_id_all(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])],
                "clean_data": [("uuid", ["2", "3", "4", "5", "6", "7", "8", "9", "10", "all"])],
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [("uuid", [5])],
            }
        )
        result = valid_schema_validator().validate(data)

        do_basic_checks(result, 1)
        filterd_results = error_counter(result)
        assert filterd_results[0].details is not None
        assert filterd_results[0].details["uuid"][0] == "all"

    def test_valid_data_not_in(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "deletion_log": [("uuid", [5])],
                "cleaning_log": [
                    ("uuid", ["1", "1", "2"]),
                ],
            }
        )
        result = valid_schema_validator(
            master_sheet="cleaning_log", child_sheets=["deletion_log"], is_in=False
        ).validate(data)

        do_basic_checks(result, 0)

    def test_invalid_data_not_in(
        self,
        valid_schema_validator: Callable[..., CrossSheetIdCheck],
    ):
        data = build_excel_data(
            {
                "deletion_log": [("uuid", [1])],
                "cleaning_log": [
                    ("uuid", ["1", "1", "2"]),
                ],
            }
        )
        result = valid_schema_validator(
            master_sheet="cleaning_log", child_sheets=["deletion_log"], is_in=False
        ).validate(data)

        do_basic_checks(result, 1)
        filterd_results = error_counter(result)
        assert filterd_results[0].details is not None
        assert filterd_results[0].details["uuid"][0] == "1"
