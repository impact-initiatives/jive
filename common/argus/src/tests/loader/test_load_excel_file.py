from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.models.base_dataset_schemas import BaseDatasetSchema
from src.argus.loaders.excel_loader import ExcelLoader
from tests.helpers import error_counter


def build_schema(
    sheet_name: str, columns: list[str], fuzzy=True, unloaded_sheet: str | None = None
):
    column_map: list[SchemaColumnMap] = []
    for column in columns:
        column_map.append(SchemaColumnMap(standard_name=column, allow_fuzzy_matching=fuzzy))

    if unloaded_sheet is None:
        l_unloaded_sheet = []
    else:
        l_unloaded_sheet = [SchemaSheetMap(standard_name=unloaded_sheet)]

    return BaseDatasetSchema(
        programme_type="jmmi",
        output_type="dataset",
        loaded_sheets=[
            SchemaSheetMap(standard_name=sheet_name, columns=column_map, allow_fuzzy_matching=fuzzy)
        ],
        unloaded_sheets=l_unloaded_sheet,
    )


@dataclass(slots=True)
class MockSheetConfig:
    name: str
    visible: str = "visible"  # "visible" or "hidden"
    data: pl.DataFrame | None = None


@pytest.fixture
def mock_fastexcel():

    @contextmanager
    def _create(sheet_configs: list[MockSheetConfig]):
        # Build all mock sheets from the config list
        sheets_by_name: dict[str, MagicMock] = {}

        for cfg in sheet_configs:
            mock_sheet = MagicMock()
            mock_sheet.visible = cfg.visible
            mock_sheet.to_polars.return_value = cfg.data
            sheets_by_name[cfg.name] = mock_sheet

        # Build the mock reader
        mock_reader = MagicMock()
        mock_reader.sheet_names = [cfg.name for cfg in sheet_configs]

        # Route load_sheet(name) to the correct mock
        mock_reader.load_sheet.side_effect = lambda sheet_name, **kwargs: sheets_by_name[sheet_name]

        # Build the top-level fastexcel mock
        with patch("src.argus.loaders.excel_loader.fastexcel") as mock_f:
            mock_f.read_excel.return_value = mock_reader
            yield {
                "fastexcel": mock_f,
                "reader": mock_reader,
                "sheets": sheets_by_name,
            }

    return _create


class TestLoadData:
    def test_valid_file(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            )
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 0
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(error_counter(results)) == 0

    def test_valid_file_upper(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"], fuzzy=False)
        sheet_data = [
            MockSheetConfig(
                name="Clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            )
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 0
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(error_counter(results)) == 0

    def test_valid_file_fuzzy_sheet(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_dataf",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            )
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 1
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(error_counter(results)) == 0

    def test_valid_file_fuzzy_column(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"_uuid": [1, 2]}),
            )
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 1
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(error_counter(results)) == 0

    def test_duplicate_columns(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1], "column_a": [1], "column_A": [1]}),
            )
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 1
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is None
            assert len(error_counter(results)) == 1
            assert results[0].details is not None
            assert len(results[0].details["duplicate_columns"]) == 1

    def test_load_all(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
            MockSheetConfig(
                name="some_other_sheet",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"), load_all_sheets=True)
            assert len(results) == 0
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called()
            assert data.get_loaded_sheet("clean_data") is not None
            assert data.get_loaded_sheet("some_other_sheet") is not None

    def test_unexpected_sheet(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
            MockSheetConfig(
                name="some_other_sheet",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 0
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(data.unexpected_sheets) == 1

    def test_unloaded_sheet(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"], unloaded_sheet="read_me")
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
            MockSheetConfig(
                name="read_me",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 0
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called_once()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(data.unloaded_sheets) == 1

    def test_hidden_sheet(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"])
        sheet_data = [
            MockSheetConfig(
                name="clean_data",
                visible="visible",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
            MockSheetConfig(
                name="clean_dataf",
                visible="hidden",
                data=pl.DataFrame({"uuid": [1, 2]}),
            ),
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 1
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_called()
            assert data.get_loaded_sheet("clean_data") is not None
            assert len(data.hidden_sheets) == 1

    def test_multiple_matches(self, mock_fastexcel):
        schema = build_schema("clean_data", ["uuid"], unloaded_sheet="clean_data2")
        sheet_data = [
            MockSheetConfig(
                name="clean_dataf",
                visible="hidden",
                data=pl.DataFrame({"uuid": [1, 2]}),
            )
        ]

        with mock_fastexcel(sheet_data) as mocks:
            data, results = ExcelLoader(schema).load(Path("/some/file.xlsx"))
            assert len(results) == 1
            mocks["fastexcel"].read_excel.assert_called_once_with(Path("/some/file.xlsx"))
            mocks["reader"].load_sheet.assert_not_called()
            assert data.get_loaded_sheet("clean_data") is None
