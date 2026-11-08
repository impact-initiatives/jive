from argus.loaders.base_excel_loader import BaseExcelLoader
from argus.models.base import SchemaColumnMap, SchemaSheetMap
from argus.validators.base import SeverityLevel
from tests.helpers import error_counter


def build_schema_sheet(
    sheet_name: str,
    sheet_alt_names: list[str],
    column: str,
    column_alt_names: list[str],
    fuzzy=True,
    matching_term: str | None = None,
    matching_term_ignore: list[str] | None = None,
):
    column_map: list[SchemaColumnMap] = []
    column_map.append(
        SchemaColumnMap(
            standard_name=column, alternate_names=column_alt_names, allow_fuzzy_matching=fuzzy
        )
    )

    l_matching_term_ignore: list[str] = []
    if matching_term_ignore is not None:
        l_matching_term_ignore = matching_term_ignore

    return SchemaSheetMap(
        standard_name=sheet_name,
        alternate_names=sheet_alt_names,
        columns=column_map,
        allow_fuzzy_matching=fuzzy,
        matching_term=matching_term,
        matching_term_ignore=l_matching_term_ignore,
    )


class TestColumnMatching:
    def test_literal_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(["uuid"], schema)
        assert len(results) == 0
        assert len(columns) == 1
        assert columns[0].schema_column_name == "uuid"
        assert columns[0].data_column_name == "uuid"

    def test_literal_match_found_alt(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=["_uuid"],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(["_uuid"], schema)
        assert len(results) == 0
        assert len(columns) == 1
        assert columns[0].schema_column_name == "uuid"
        assert columns[0].data_column_name == "_uuid"

    def test_no_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(["some_column"], schema)
        assert len(results) == 0
        assert len(columns) == 0

    def test_fuzzy_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=True,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(["_uuid"], schema)
        assert len(results) == 1
        assert results[0].severity == SeverityLevel.INFO
        assert len(columns) == 1
        assert columns[0].schema_column_name == "uuid"
        assert columns[0].data_column_name == "_uuid"

    def test_fuzzy_match_found_alt(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="some_column",
            column_alt_names=["uuid"],
            fuzzy=True,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(["_uuid"], schema)
        assert len(results) == 1
        assert results[0].severity == SeverityLevel.INFO
        assert len(columns) == 1
        assert columns[0].schema_column_name == "some_column"
        assert columns[0].data_column_name == "_uuid"

    def test_multiple_fuzzy_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="some_column",
            column_alt_names=[],
            fuzzy=True,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(
            ["somecolumn", "_some_column", "_somecolumn"], schema
        )
        assert len(error_counter(results)) == 1
        assert len(columns) == 0

    def test_multiple_literal_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=["_uuid"],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        results, columns = loader.match_excel_columns_to_schema(["uuid", "_uuid"], schema)
        assert len(error_counter(results)) == 1
        assert len(columns) == 0
        assert results[0].details is not None
        assert "uuid" in results[0].details["Literal Match Columns"]
        assert "_uuid" in results[0].details["Literal Match Columns"]


class TestSheetMatching:
    def test_literal_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("clean_data", [schema])
        assert len(results) == 0
        assert sheet == "clean_data"

    def test_no_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("some_sheet", [schema])
        assert len(results) == 0
        assert sheet == ""

    def test_literal_match_found_alt(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=["cleaned_data"],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("cleaned_data", [schema])
        assert len(results) == 0
        assert sheet == "clean_data"

    def test_literal_match_found_different_case(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("Clean_Data", [schema])
        assert len(results) == 0
        assert sheet == "clean_data"

    def test_fuzzy_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=True,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("cleandata", [schema])
        assert len(results) == 1
        assert results[0].severity == SeverityLevel.INFO
        assert sheet == "clean_data"

    def test_multiple_fuzzy_match_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=True,
            matching_term=None,
            matching_term_ignore=None,
        )
        schema2 = build_schema_sheet(
            sheet_name="_cleandata",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=True,
            matching_term=None,
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("cleandata", [schema, schema2])
        assert len(results) == 1
        assert results[0].severity == SeverityLevel.INFO
        assert sheet == ""
        assert results[0].details is not None

    def test_matching_term_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term="clean",
            matching_term_ignore=None,
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("clean_version_1", [schema])
        assert len(results) == 1
        assert results[0].severity == SeverityLevel.INFO
        assert sheet == "clean_data"

    def test_matching_term_ignore_found(self):
        schema = build_schema_sheet(
            sheet_name="clean_data",
            sheet_alt_names=[],
            column="uuid",
            column_alt_names=[],
            fuzzy=False,
            matching_term="clean",
            matching_term_ignore=["version"],
        )
        loader = BaseExcelLoader()
        sheet, results = loader.match_excel_sheet_to_schema("clean_version_1", [schema])
        assert len(results) == 0
        assert sheet == ""
