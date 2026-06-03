import polars as pl
import xlsxwriter
from pathlib import Path
from rqa_validator.models.api_models import PipelineResponse
from logger import get_logger

logger = get_logger("jive.excel_exporter")

def export_response_to_excel(response: PipelineResponse, output_path: Path):
    """
    Exports the validation results into a multi-sheet Excel file.
    Sheet 1: 'Validation Summary' (High-level errors and warnings)
    Sheet 2: 'Detailed Findings' (Expanded rows for row-level details)
    """
    def _get_field(item, field: str, default=None):
        if isinstance(item, dict):
            return item.get(field, default)
        return getattr(item, field, default)

    summary_rows = []
    detail_dfs = []
    
    #Consolidate results
    all_issues: list[dict | object] = []
    
    errors = getattr(response, 'errors', [])
    admin_errors = getattr(response, 'admin_errors', [])
    warnings = getattr(response, 'warnings', [])
    info = getattr(response, 'info', [])
    
    all_issues.extend(admin_errors)
    all_issues.extend(errors)
    all_issues.extend(warnings)
    all_issues.extend(info)

    if not all_issues:
        #Empty excel file with headers for the summary sheet if there are no issues
        df = pl.DataFrame(
            schema={
                "Severity": pl.String,
                "Rule": pl.String,
                "Sheet Name": pl.String,
                "Column Name": pl.String,
                "Message": pl.String,
            }
        )
        with xlsxwriter.Workbook(str(output_path)) as workbook:
            df.write_excel(workbook=workbook, worksheet="Validation Summary")
        return

    for item in all_issues:
        # Pydantic/ Dict safety
        severity = (_get_field(item, "severity") or "").upper()
        rule = _get_field(item, "rule", "")
        sheet_name = _get_field(item, "sheet_name", "")
        col_name = _get_field(item, "column_name", "")
        message = _get_field(item, "message", "")
        details = _get_field(item, "details", None)

        summary_rows.append({
            "Severity": severity,
            "Rule": rule,
            "Sheet Name": sheet_name or "",
            "Column Name": col_name or "",
            "Message": message
        })

        if details and isinstance(details, dict) and any(isinstance(v, list) for v in details.values()):
            try:
                df = pl.DataFrame(details)
                df = df.with_columns(pl.all().cast(pl.String))
                df = df.with_columns([
                    pl.lit(severity).alias("Severity"),
                    pl.lit(rule).alias("Rule")
                ])
                cols = ["Severity", "Rule"] + [c for c in df.columns if c not in ["Severity", "Rule"]]
                df = df.select(cols)
                detail_dfs.append(df)
            except Exception as e:
                logger.warning(
                    "Failed to expand details for rule '%s' into DataFrame — skipping. Error: %s",
                    rule,
                    e,
                )

    df_summary = pl.DataFrame(summary_rows)

    if detail_dfs:
        df_details = pl.concat(detail_dfs, how="diagonal")
    else:
        df_details = pl.DataFrame({"Notice": ["No detailed row-level findings generated."]})

    with xlsxwriter.Workbook(str(output_path)) as workbook:
        # Format for header
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'bg_color': '#D3D3D3',
            'border': 1
        })
        
        df_summary.write_excel(
            workbook=workbook, 
            worksheet="Validation Summary",
            header_format=header_format,
            autofit=True
        )
        
        df_details.write_excel(
            workbook=workbook, 
            worksheet="Detailed Findings",
            header_format=header_format,
            autofit=True
        )
