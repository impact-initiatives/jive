import pytest

from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.base import BaseValidator
from argus.validators.common_validators import (
    CrossSheetRowSumCheck,
)
from tests.helpers import build_excel_data, do_basic_checks


@pytest.fixture
def valid_schema_validator(valid_schema):
    """Create a UniqueColumn validator instance"""
    return CrossSheetRowSumCheck(schema=valid_schema)


@pytest.fixture
def invalid_args_validator(valid_schema):
    """Create a UniqueColumn validator instance"""
    return CrossSheetRowSumCheck(schema=valid_schema, master_sheet="invalid_sheet")


@pytest.fixture
def valid_schema_child_validator(valid_schema_child):
    """Create a UniqueColumn validator instance"""
    return CrossSheetRowSumCheck(
        schema=valid_schema_child,
        master_sheet="raw_data_child",
        child_sheets=["clean_data_child"],
        master_deletion_log="deletion_log",
    )


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
                        alternate_names=["uuidx", "X_uuid", "uuid2"],
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
                        is_unique=True,
                    )
                ],
            ),
        ],
        unloaded_sheets=[],
    )


@pytest.fixture
def valid_schema_child():

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name="raw_data_child",
                alternate_names=["raw_data_child"],
                columns=[
                    SchemaColumnMap(
                        standard_name="person_id",
                        is_unique=True,
                    ),
                    SchemaColumnMap(
                        standard_name="uuid",
                    ),
                ],
                parent_sheet="raw_data",
                parent_linking_column="uuid",
            ),
            SchemaSheetMap(
                standard_name="clean_data_child",
                alternate_names=["clean_data_child"],
                columns=[
                    SchemaColumnMap(
                        standard_name="person_id",
                        is_unique=True,
                    ),
                    SchemaColumnMap(
                        standard_name="uuid",
                    ),
                ],
            ),
            SchemaSheetMap(
                standard_name="raw_data",
                alternate_names=["raw_data"],
                columns=[
                    SchemaColumnMap(
                        standard_name="uuid",
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
                        is_unique=True,
                    )
                ],
            ),
        ],
        unloaded_sheets=[],
    )


class TestCrossSheetRowSum:
    def test_valid_data(
        self,
        valid_schema_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4])],
                "clean_data": [("uuid", [1, 2, 3])],
                "deletion_log": [("uuid", [4])],
            }
        )

        result = valid_schema_validator.validate(data)

        do_basic_checks(result, 0)

    def test_valid_data_no_deletions(
        self,
        valid_schema_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4])],
                "clean_data": [("uuid", [1, 2, 3, 4])],
                "deletion_log": [("uuid", [])],
            }
        )

        result = valid_schema_validator.validate(data)

        do_basic_checks(result, 0)

    def test_missing_deleted_data(
        self,
        valid_schema_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4])],
                "clean_data": [("uuid", [1, 2, 3])],
                "deletion_log": [("uuid", [])],
            }
        )
        result = valid_schema_validator.validate(data)

        do_basic_checks(result, 1)

    def test_missing_clean_data(
        self,
        valid_schema_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4])],
                "clean_data": [
                    (
                        "uuid",
                        [
                            1,
                            2,
                        ],
                    )
                ],
                "deletion_log": [("uuid", [4])],
            }
        )
        result = valid_schema_validator.validate(data)

        do_basic_checks(result, 1)

    def test_missing_sheet_data(
        self,
        valid_schema_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4])],
                "clean_data": [
                    (
                        "uuid",
                        [
                            1,
                            2,
                        ],
                    )
                ],
                "missing_sheet": [("uuid", [4])],
            }
        )
        result = valid_schema_validator.validate(data)

        do_basic_checks(result, 1)

    def test_valid_parent_child_data(
        self,
        valid_schema_child_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "deletion_log": [("uuid", [1])],
            }
        )
        result = valid_schema_child_validator.validate(data)

        do_basic_checks(result, 0)

    def test_valid_parent_child_data_no_deletions(
        self,
        valid_schema_child_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "raw_data": [("uuid", [2, 3, 4, 5])],
                "clean_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "deletion_log": [("uuid", [])],
            }
        )
        result = valid_schema_child_validator.validate(data)

        do_basic_checks(result, 0)

    def test_invalid_parent_child_data(
        self,
        valid_schema_child_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data_child": [("uuid", [2, 2, 3]), ("person_id", [1, 2, 3])],
                "deletion_log": [("uuid", [1])],
            }
        )
        result = valid_schema_child_validator.validate(data)

        do_basic_checks(result, 1)

    def test_parent_child_data_missing_id_column(
        self,
        valid_schema_child_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "deletion_log": [("missing_column", [1])],
            }
        )
        result = valid_schema_child_validator.validate(data)

        do_basic_checks(result, 1)

    def test_incorrect_sheet(
        self,
        invalid_args_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data": [("uuid", [1, 2, 3, 4])],
                "clean_data": [("uuid", [1, 2, 3])],
                "deletion_log": [("uuid", [4])],
            }
        )
        result = invalid_args_validator.validate(data)

        do_basic_checks(result, 1)

    def test_parent_child_data_missing_deletion_sheet(
        self,
        valid_schema_child_validator: BaseValidator,
    ):
        data = build_excel_data(
            {
                "raw_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
                "raw_data": [("uuid", [1, 2, 3, 4, 5])],
                "clean_data_child": [("uuid", [2, 2, 3, 4]), ("person_id", [1, 2, 3, 4])],
            }
        )
        result = valid_schema_child_validator.validate(data)

        do_basic_checks(result, 1)
