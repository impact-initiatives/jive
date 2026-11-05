from unittest.mock import Mock, patch

from argus.models.base import SheetClassification
from argus.models.base_dataset import BaseDataset
from argus.models.base_dataset_schemas import BaseDatasetSchema
from argus.validators.base import BaseValidator
from tests.helpers import build_schema_with_attributes


def get_dataset(schema: dict[str, dict[str, str]]):

    mock_schema = Mock(spec=BaseDatasetSchema)
    mock_validator = Mock(spec=[BaseValidator])

    with (
        patch.object(BaseDataset, "get_schema", return_value=mock_schema),
        patch.object(BaseDataset, "get_validators", return_value=[mock_validator]),
    ):
        dataset = BaseDataset("", "")
        dataset.schema = build_schema_with_attributes(schema)
        dataset._sort_sheets()
        return dataset.validate_schema_links()


class TestSchemaValidation:
    def test_valid_data(self):
        schema = {
            "clean_data": {
                "linked_sheet": "raw_data",
                "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                "linked_sheet": "clean_data",
                "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 0

    def test_valid_data_only_clean(self):
        schema = {
            "clean_data": {
                # "linked_sheet": "raw_data",
                # "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 0

    def test_missing_raw_link(self):
        schema = {
            "clean_data": {
                # "linked_sheet": "raw_data",
                "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                "linked_sheet": "clean_data",
                "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert results[0].details["sheet"][0] == "clean_data"
        assert "No linked 'raw_data' sheet" in results[0].details["issue"]

    def test_missing_clean_link(self):
        schema = {
            "clean_data": {
                "linked_sheet": "raw_data",
                "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                # "linked_sheet": "clean_data",
                "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert results[0].details["sheet"][0] == "raw_data"
        assert "No linked 'clean_data' sheet" in results[0].details["issue"]

    def test_missing_cleaning_link(self):
        schema = {
            "clean_data": {
                "linked_sheet": "raw_data",
                # "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                "linked_sheet": "clean_data",
                "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert results[0].details["sheet"][0] == "clean_data"
        assert "No linked 'cleaning_log' sheet" in results[0].details["issue"]

    def test_missing_deletion_link(self):
        schema = {
            "clean_data": {
                "linked_sheet": "raw_data",
                "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                "linked_sheet": "clean_data",
                # "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert results[0].details["sheet"][0] == "raw_data"
        assert "No linked 'deletion_log' sheet" in results[0].details["issue"]

    def test_missing_parent_link_cleaning(self):
        schema = {
            "clean_data": {
                "linked_sheet": "raw_data",
                "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                "linked_sheet": "clean_data",
                "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                # "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert results[0].details["sheet"][0] == "cleaning_log"
        assert "No linked 'clean_data' sheet" in results[0].details["issue"]

    def test_missing_parent_link_deletion(self):
        schema = {
            "clean_data": {
                "linked_sheet": "raw_data",
                "linked_log": "cleaning_log",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "raw_data": {
                "linked_sheet": "clean_data",
                "linked_log": "deletion_log",
                "classification": SheetClassification.RAW_DATA_SHEET,
            },
            "cleaning_log": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEANING_LOG_SHEET,
            },
            "deletion_log": {
                # "parent_sheet": "raw_data",
                "classification": SheetClassification.DELETION_LOG_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert results[0].details["sheet"][0] == "deletion_log"
        assert "No linked 'raw_data' sheet" in results[0].details["issue"]

    def test_multiple_parents(self):
        schema = {
            "clean_data": {
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "clean_data_2": {
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert results[0].details is not None
        assert "sheets did not match to a parent" in results[0].message

    def test_multiple_parent_match(self):
        schema = {
            "clean_data": {
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "clean_data2": {
                "parent_sheet": "clean_data",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
            "clean_data3": {
                "parent_sheet": "clean_data2",
                "classification": SheetClassification.CLEAN_DATA_SHEET,
            },
        }

        results = get_dataset(schema)
        assert len(results) == 1
        assert "There should only be 1 parent sheet" in results[0].message
