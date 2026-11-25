import polars as pl
from argus.orchestrator.output_models import (  # noqa: E402
    MetadataModel,
    PipelineResponse,
    SummaryModel,
)
from argus.validators.base import SeverityLevel, ValidationResult, ValidatorResponse

from ..validator.excel_exporter import export_response_to_excel  # noqa: E402


def test_export_empty_response(tmp_path):
    response = PipelineResponse.model_construct(
        success=True,
        summary={
            "passed": True,
            "admin_errors": 0,
            "errors": 0,
            "warnings": 0,
            "info": 0,
        },
        metadata=MetadataModel.model_construct(
            programme_type="jmmi",
            output_type="dataset",
            file_name="some_dataset.xlsx",
            validation_date="20260101",
        ),
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
        summary=SummaryModel(
            passed=False,
            admin_errors=0,
            errors=1,
            warnings=1,
            info=0,
            admin_info=0,
        ),
        metadata=MetadataModel.model_construct(
            programme_type="jmmi",
            output_type="dataset",
            file_name="data.xlsx",
            validation_date="20260101",
        ),
        warnings=[
            ValidatorResponse(
                name="test",
                details=[
                    ValidationResult(
                        severity=SeverityLevel.WARNING,
                        message="Warning msg",
                        sheet_name="S1",
                        column_name="C1",
                    )
                ],
            )
        ],
        errors=[
            ValidatorResponse(
                name="E1",
                details=[
                    ValidationResult(
                        severity=SeverityLevel.ERROR,
                        message="Error msg",
                        details={"Row": [1, 2], "Value": ["a", "b"]},
                    )
                ],
            )
        ],
        info=[
            ValidatorResponse(
                name="test",
                details=[ValidationResult(severity=SeverityLevel.INFO, message="Info msg")],
            )
        ],
        admin_errors=[
            ValidatorResponse(
                name="E1",
                details=[ValidationResult(severity=SeverityLevel.ADMIN_INFO, message="Admin msg")],
            )
        ],
        passed=[],
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
        summary=SummaryModel(
            passed=False,
            admin_errors=0,
            errors=1,
            warnings=0,
            info=0,
            admin_info=0,
        ),
        metadata=MetadataModel.model_construct(
            programme_type="jmmi",
            output_type="dataset",
            file_name="data.xlsx",
            validation_date="20260101",
        ),
        errors=[
            ValidatorResponse(
                name="test",
                details=[
                    ValidationResult(
                        severity=SeverityLevel.ERROR,
                        message="Error msg",
                        details={
                            "Row": 1,
                            "Value": "a",  # Not a list, should be caught by exception handling
                        },
                    )
                ],
            )
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
