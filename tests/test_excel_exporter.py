import polars as pl

from excel_exporter import export_response_to_excel
from models import PipelineResponse


def test_export_empty_response(tmp_path):
    response = PipelineResponse.model_construct(
        success=True,
        summary={"passed": True, "admin_errors": 0, "errors": 0, "warnings": 0, "info": 0},
        metadata={"dataset_type": "msna"},
        warnings=[],
        errors=[],
        info=[],
        admin_errors=[],
    )
    output_path = tmp_path / "empty_report.xlsx"

    export_response_to_excel(response, output_path)

    assert output_path.exists()

    # Read the summary sheet
    df_summary = pl.read_excel(output_path, sheet_name="Validation Summary")
    assert df_summary.is_empty()
    assert "Severity" in df_summary.columns
    assert "Rule" in df_summary.columns


def test_export_populated_response(tmp_path):
    response = PipelineResponse.model_construct(
        success=False,
        summary={"passed": False, "admin_errors": 0, "errors": 1, "warnings": 1, "info": 0},
        metadata={"dataset_type": "msna"},
        warnings=[
            {
                "severity": "warning",
                "rule": "W1",
                "message": "Warning msg",
                "sheet_name": "S1",
                "column_name": "C1",
            }
        ],
        errors=[
            {
                "severity": "error",
                "rule": "E1",
                "message": "Error msg",
                "details": {"Row": [1, 2], "Value": ["a", "b"]},
            }
        ],
        info=[{"severity": "info", "rule": "I1", "message": "Info msg"}],
        admin_errors=[{"severity": "admin", "rule": "A1", "message": "Admin msg"}],
    )
    output_path = tmp_path / "populated_report.xlsx"

    export_response_to_excel(response, output_path)

    assert output_path.exists()

    df_summary = pl.read_excel(output_path, sheet_name="Validation Summary")
    assert len(df_summary) == 4

    df_details = pl.read_excel(output_path, sheet_name="Details - E1")
    assert len(df_details) == 2  # Two rows from the 'details' dict in the error
    assert "Row" in df_details.columns
    assert "Value" in df_details.columns


def test_export_invalid_details(tmp_path):
    # Tests that details missing list arrays don't crash the exporter
    response = PipelineResponse.model_construct(
        success=False,
        summary={"passed": False, "admin_errors": 0, "errors": 1, "warnings": 0, "info": 0},
        metadata={"dataset_type": "msna"},
        errors=[
            {
                "severity": "error",
                "rule": "E1",
                "message": "Error msg",
                "details": {
                    "Row": 1,
                    "Value": "a",
                },  # Not a list, should be caught by exception handling
            }
        ],
        warnings=[],
        info=[],
        admin_errors=[],
    )
    output_path = tmp_path / "invalid_details.xlsx"

    export_response_to_excel(response, output_path)

    assert output_path.exists()

    df_summary = pl.read_excel(output_path, sheet_name="Validation Summary")
    assert len(df_summary) == 1

    # Detailed findings should just have the fallback notice since expanding failed
    df_details = pl.read_excel(output_path, sheet_name="Detailed Findings")
    assert "Notice" in df_details.columns
    assert "No detailed row-level findings generated." in str(df_details["Notice"][0])
