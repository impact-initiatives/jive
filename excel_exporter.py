import os
from pathlib import Path

import polars as pl
import xlsxwriter

from logger import get_logger
from models import PipelineResponse

logger = get_logger("jive.excel_exporter")


def export_response_to_excel(
    response: PipelineResponse, output_path: Path, max_excel_errors: int = 50000
):
    """
    Exports the validation results into a multi-sheet Excel file.
    Sheet 1: 'Validation Summary' (High-level errors and warnings)
    Sheet 2+: 'Details - <Rule>' (One sheet per rule with row-level detail findings)
    """

    def _get_field(item, field: str, default=None):
        if isinstance(item, dict):
            return item.get(field, default)
        return getattr(item, field, default)

    summary_rows = []
    rule_detail_dfs = {}
    total_detail_rows = 0
    MAX_ROWS = int(os.getenv("MAX_EXCEL_ERRORS", max_excel_errors))
    truncated = False

    # Consolidate results
    all_issues: list[dict | object] = []

    errors = getattr(response, "errors", [])
    admin_errors = getattr(response, "admin_errors", [])
    warnings = getattr(response, "warnings", [])
    info = getattr(response, "info", [])

    all_issues.extend(admin_errors)
    all_issues.extend(errors)
    all_issues.extend(warnings)
    all_issues.extend(info)

    if not all_issues:
        # Empty excel file with headers for the summary sheet if there are no issues
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
        rule = _get_field(item, "rule", "Unknown_Rule")
        sheet_name = _get_field(item, "sheet_name", "")
        col_name = _get_field(item, "column_name", "")
        message = _get_field(item, "message", "")
        details = _get_field(item, "details", None)

        summary_rows.append(
            {
                "Severity": severity,
                "Rule": rule,
                "Sheet Name": sheet_name or "",
                "Column Name": col_name or "",
                "Message": message,
            }
        )

        if (
            details
            and isinstance(details, dict)
            and any(isinstance(v, list) for v in details.values())
        ):
            if total_detail_rows >= MAX_ROWS:
                truncated = True
                continue

            try:
                safe_details = {}
                for k, v in details.items():
                    if isinstance(v, list):
                        safe_details[k] = [str(item) if item is not None else "" for item in v]
                    else:
                        safe_details[k] = [str(v)]

                df = pl.DataFrame(safe_details)
                # Check if this df puts us over the limit
                if total_detail_rows + len(df) > MAX_ROWS:
                    df = df.head(MAX_ROWS - total_detail_rows)
                    truncated = True
                df = df.with_columns(pl.all().cast(pl.String))

                if rule not in rule_detail_dfs:
                    rule_detail_dfs[rule] = []

                rule_detail_dfs[rule].append(df)
                total_detail_rows += len(df)
            except Exception as e:
                logger.warning(
                    "Failed to expand details for rule '%s' into DataFrame — skipping. Error: %s",
                    rule,
                    e,
                )

    if truncated:
        summary_rows.insert(
            0,
            {
                "Severity": "WARNING",
                "Rule": "Export Truncated",
                "Sheet Name": "",
                "Column Name": "",
                "Message": f"The dataset generated too many errors. Detailed findings have been"
                f" truncated to the first {MAX_ROWS} rows to prevent memory exhaustion.",
            },
        )

    df_summary = pl.DataFrame(summary_rows)

    with xlsxwriter.Workbook(str(output_path)) as workbook:
        # Format for header
        header_format = workbook.add_format(
            {"bold": True, "text_wrap": True, "valign": "top", "bg_color": "#D3D3D3", "border": 1}
        )

        df_summary.write_excel(
            workbook=workbook,
            worksheet="Validation Summary",
            header_format=header_format.__dict__,
            autofit=True,
        )

        if rule_detail_dfs:
            used_sheet_names = {"Validation Summary"}
            for rule, dfs in rule_detail_dfs.items():
                try:
                    # Try vertical first (assuming schemas match)
                    df_details = pl.concat(dfs, how="vertical")
                except Exception as e:
                    # If columns differ across issues for the same rule, fall back to diagonal
                    logger.warning(
                        "Falling back to diagonal concat for rule %s due to schema mismatch: %s",
                        rule,
                        e,
                    )
                    try:
                        df_details = pl.concat(dfs, how="diagonal")
                    except Exception as fallback_e:
                        logger.error(
                            "Failed to concatenate details for rule %s: %s", rule, fallback_e
                        )
                        continue

                # Excel sheet names have a 31 character limit and cannot contain certain characters
                # We'll prepend 'Details - ' and truncate if necessary
                base_sheet_name = f"Details - {rule}"
                safe_sheet_name = "".join(c for c in base_sheet_name if c not in r"[]:*?/\'")[:31]

                # Ensure uniqueness
                final_sheet_name = safe_sheet_name
                counter = 1
                while final_sheet_name in used_sheet_names:
                    suffix = f"_{counter}"
                    final_sheet_name = f"{safe_sheet_name[: 31 - len(suffix)]}{suffix}"
                    counter += 1

                used_sheet_names.add(final_sheet_name)

                df_details.write_excel(
                    workbook=workbook,
                    worksheet=final_sheet_name,
                    header_format=header_format,
                    autofit=True,
                )
        else:
            df_details = pl.DataFrame({"Notice": ["No detailed row-level findings generated."]})
            df_details.write_excel(
                workbook=workbook,
                worksheet="Detailed Findings",
                header_format=header_format.__dict__,
                autofit=True,
            )
