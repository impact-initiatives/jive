from pathlib import Path, PosixPath

import polars as pl
import pytest

from argus.config import settings
from argus.loaders.base import (
    DataSheetMap,
)
from argus.loaders.base_excel_loader import ExcelLoaderData
from argus.models.base import SheetClassification
from argus.models.dynamic_schema import DynamicDataset
from argus.models.resolver import find_dataset_files
from argus.utils.yaml_loader import download_config
from tests.helpers import admin_error_counter, error_counter


@pytest.fixture
def valid_dataset():
    """Create a UniqueColumn validator instance"""
    dataset_config_directory = download_config(settings.DATASET_CONFIG_DIR)
    result = find_dataset_files(
        dataset_config_directory, "other", "dataset", "en", "schema.yaml", "validators.yaml"
    )
    assert result is not None
    dataset: DynamicDataset = DynamicDataset(
        schema_path=result["schema.yaml"], validator_path=result["validators.yaml"]
    )
    return {
        "dataset": dataset,
        "dataset_config_directory": dataset_config_directory,
    }


@pytest.fixture
def valid_excel_data():
    """Create ExcelLoaderData with matching columns"""

    df_clean_main = pl.DataFrame(
        {
            "uuid": [1, 2, 3, 4, 5],
        }
    )

    df_raw_main = pl.DataFrame(
        {
            "uuid": [1, 2, 3, 4, 5],
        }
    )

    df_clean_child = pl.DataFrame(
        {
            "uuid": [1, 1, 3, 4, 4],
            "child_id": [1, 2, 3, 4, 5],
        }
    )

    df_raw_child = pl.DataFrame(
        {
            "uuid": [1, 1, 3, 4, 4],
            "child_id": [1, 2, 3, 4, 5],
        }
    )

    df_clean_log_main = pl.DataFrame(
        {
            "uuid": [5],
        }
    )

    df_clean_log_child = pl.DataFrame(
        {
            "child_id": [5],
        }
    )

    df_deletion_log_main = pl.DataFrame(
        {
            "uuid": [5],
        }
    )

    df_deletion_log_child = pl.DataFrame(
        {
            "child_id": [5],
        }
    )

    loaded_sheets = [
        DataSheetMap(
            schema_sheet_name="main_clean_data",
            data_sheet_name="main_clean_data",
            data=df_clean_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="main_raw_data",
            data_sheet_name="main_raw_data",
            data=df_raw_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="main_cleaning_log",
            data_sheet_name="main_cleaning_log",
            data=df_clean_log_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="child_cleaning_log",
            data_sheet_name="child_cleaning_log",
            data=df_clean_log_child,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="child_deletion_log",
            data_sheet_name="child_deletion_log",
            data=df_deletion_log_child,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="main_deletion_log",
            data_sheet_name="main_deletion_log",
            data=df_deletion_log_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="survey",
            data_sheet_name="survey",
        ),
        DataSheetMap(
            schema_sheet_name="choices",
            data_sheet_name="choices",
        ),
        DataSheetMap(
            schema_sheet_name="child_clean_data",
            data_sheet_name="child_clean_data",
            data=df_clean_child,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="child_raw_data",
            data_sheet_name="child_raw_data",
            data=df_raw_child,
            auto_loaded=True,
        ),
    ]
    unloaded_sheets = [
        DataSheetMap(
            schema_sheet_name="read_me",
            data_sheet_name="read_me",
        ),
    ]

    return ExcelLoaderData(loaded_sheets=loaded_sheets, unloaded_sheets=unloaded_sheets)


@pytest.fixture
def invalid_excel_data():
    """Create ExcelLoaderData with matching columns"""

    df_clean_main = pl.DataFrame(
        {
            "uuid": [1, 2, 3, 4, 5],
        }
    )

    df_raw_main = pl.DataFrame(
        {
            "uuid": [1, 2, 3, 4, 5],
        }
    )

    df_clean_child = pl.DataFrame(
        {
            "uuid": [1, 1, 3, 4, 4],
            "child_id": [1, 2, 3, 4, 5],
            "child_id2": [1, 2, 3, 4, 5],
        }
    )

    df_raw_child = pl.DataFrame(
        {
            "uuid": [11, 11, 43, 44, 34],
            "child_id": [11, 22, 33, 44, 55],
        }
    )

    df_clean_log_main = pl.DataFrame(
        {
            "uuid": [5],
        }
    )

    df_clean_log_child = pl.DataFrame(
        {
            "child_id": [5],
        }
    )

    df_deletion_log_main = pl.DataFrame(
        {
            "uuid": [5],
        }
    )

    df_deletion_log_child = pl.DataFrame(
        {
            "child_id": [5],
        }
    )

    loaded_sheets = [
        DataSheetMap(
            schema_sheet_name="main_clean_data",
            data_sheet_name="main_clean_data",
            data=df_clean_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="main_raw_data",
            data_sheet_name="main_raw_data",
            data=df_raw_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="main_cleaning_log",
            data_sheet_name="main_cleaning_log",
            data=df_clean_log_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="child_cleaning_log",
            data_sheet_name="child_cleaning_log",
            data=df_clean_log_child,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="child_deletion_log",
            data_sheet_name="child_deletion_log",
            data=df_deletion_log_child,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="main_deletion_log",
            data_sheet_name="main_deletion_log",
            data=df_deletion_log_main,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="survey",
            data_sheet_name="survey",
        ),
        DataSheetMap(
            schema_sheet_name="choices",
            data_sheet_name="choices",
        ),
        DataSheetMap(
            schema_sheet_name="child_clean_data",
            data_sheet_name="child_clean_data",
            data=df_clean_child,
            auto_loaded=True,
        ),
        DataSheetMap(
            schema_sheet_name="child_raw_data",
            data_sheet_name="child_raw_data",
            data=df_raw_child,
            auto_loaded=True,
        ),
    ]
    unloaded_sheets = [
        DataSheetMap(
            schema_sheet_name="read_me",
            data_sheet_name="read_me",
        ),
    ]

    return ExcelLoaderData(loaded_sheets=loaded_sheets, unloaded_sheets=unloaded_sheets)


class TestDynamicSchema:
    def test_valid_data(
        self,
        valid_dataset: dict[str, DynamicDataset | Path],
        valid_excel_data: ExcelLoaderData,
    ):

        dataset = valid_dataset["dataset"]
        dataset_config_directory = valid_dataset["dataset_config_directory"]
        assert isinstance(dataset_config_directory, PosixPath)
        assert isinstance(dataset, DynamicDataset)
        dataset.data = valid_excel_data
        results = dataset.process_data(dataset_config_directory=dataset_config_directory)
        assert len(error_counter(results)) == 0

        assert (
            len(
                [
                    item
                    for item, value in dataset.sheet_matching.items()
                    if value.classification == SheetClassification.CLEANING_LOG_SHEET
                ]
            )
            == 2
        )

        assert (
            len(
                [
                    item
                    for item, value in dataset.sheet_matching.items()
                    if value.classification == SheetClassification.CLEAN_DATA_SHEET
                ]
            )
            == 2
        )

        assert (
            len(
                [
                    item
                    for item, value in dataset.sheet_matching.items()
                    if value.classification == SheetClassification.RAW_DATA_SHEET
                ]
            )
            == 2
        )

    def test_invalid_data(
        self, valid_dataset: dict[str, DynamicDataset | Path], invalid_excel_data: ExcelLoaderData
    ):
        dataset = valid_dataset["dataset"]
        dataset_config_directory = valid_dataset["dataset_config_directory"]
        assert isinstance(dataset_config_directory, PosixPath)
        assert isinstance(dataset, DynamicDataset)

        dataset.data = invalid_excel_data
        results = dataset.process_data(dataset_config_directory=dataset_config_directory)
        assert len(admin_error_counter(results)) == 0
        assert len(error_counter(results)) == 9

        assert (
            len(
                [
                    item
                    for item, value in dataset.sheet_matching.items()
                    if value.classification == SheetClassification.CLEANING_LOG_SHEET
                ]
            )
            == 2
        )

        assert (
            len(
                [
                    item
                    for item, value in dataset.sheet_matching.items()
                    if value.classification == SheetClassification.CLEAN_DATA_SHEET
                ]
            )
            == 2
        )

        assert (
            len(
                [
                    item
                    for item, value in dataset.sheet_matching.items()
                    if value.classification == SheetClassification.RAW_DATA_SHEET
                ]
            )
            == 2
        )
