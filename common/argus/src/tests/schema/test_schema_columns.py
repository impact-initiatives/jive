from unittest.mock import Mock, patch

import pytest

from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset import BaseDataset
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.base import BaseValidator
from tests.helpers import do_basic_checks


@pytest.fixture
def valid_schema():

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name="raw_data",
                alternate_names=["raw_data"],
                columns=[SchemaColumnMap(standard_name="uuid", alternate_names=["uuid", "X_uuid"])],
            )
        ],
        unloaded_sheets=[],
    )


@pytest.fixture
def invalid_schema_duplicate_columns():

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name="raw_data",
                alternate_names=["raw_data"],
                columns=[
                    SchemaColumnMap(standard_name="uuid", alternate_names=["uuid", "X_uuid"]),
                    SchemaColumnMap(standard_name="uuid", alternate_names=["uuid", "X_uuid"]),
                ],
            )
        ],
        unloaded_sheets=[],
    )


@pytest.fixture
def invalid_schema_duplicate_columns_alt():

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(
                standard_name="raw_data",
                alternate_names=["raw_data"],
                columns=[
                    SchemaColumnMap(standard_name="uuid", alternate_names=["uuid", "X_uuid"]),
                    SchemaColumnMap(standard_name="other", alternate_names=["uuid"]),
                ],
            )
        ],
        unloaded_sheets=[],
    )


def validate_schema(schema: BaseDatasetSchema):

    mock_schema = Mock(spec=BaseDatasetSchema)
    mock_validator = Mock(spec=[BaseValidator])

    with (
        patch.object(BaseDataset, "get_schema", return_value=mock_schema),
        patch.object(BaseDataset, "get_validators", return_value=[mock_validator]),
    ):
        dataset = BaseDataset("", "")
        dataset.schema = schema
        return dataset.validate_schema_item_names()


class TestSchemaColumns:
    def test_valid_schema(self, valid_schema: BaseDatasetSchema):
        result = validate_schema(valid_schema)

        do_basic_checks(result, 0)

    def test_duplicate_columns(self, invalid_schema_duplicate_columns: BaseDatasetSchema):
        result = validate_schema(invalid_schema_duplicate_columns)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["columns"]) == 2

    def test_duplicate_columns_alt(self, invalid_schema_duplicate_columns_alt: BaseDatasetSchema):
        result = validate_schema(invalid_schema_duplicate_columns_alt)

        do_basic_checks(result, 1)
        assert result[0].details is not None
        assert len(result[0].details["columns"]) == 1
