import os
from pathlib import Path
from typing import Any

import polars as pl
import xlsxwriter

from .logger import get_logger
from .models import PipelineResponse, ResultItemModel

logger = get_logger("jive.excel_exporter")


def export_response_to_excel(
    response: PipelineResponse, output_path: Path, max_excel_errors: int = 50000
):
    """
    Exports the validation results into a multi-sheet Excel file.
    Sheet 1: 'Validation Summary' (High-level errors and warnings)
    Sheet 2+: 'Details - <Rule>' (One sheet per rule with row-level detail findings)
    """

    summary_rows: list[dict[str, Any]] = []
    rule_detail_dfs: dict[str, list[pl.DataFrame]] = {}
    total_detail_rows = 0
    MAX_ROWS = int(os.getenv("MAX_EXCEL_ERRORS", max_excel_errors))
    truncated = False

    # Consolidate results
    all_issues: list[ResultItemModel] = []

    all_issues.extend(response.admin_errors)
    all_issues.extend(response.errors)
    all_issues.extend(response.warnings)
    all_issues.extend(response.info)

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
            _ = df.write_excel(workbook=workbook, worksheet="Validation Summary")
        return

    for item in all_issues:
        # Pydantic/ Dict safety

        summary_rows.append(
            {
                "Severity": item.severity,
                "Rule": item.rule,
                "Sheet Name": item.sheet_name if item.sheet_name is not None else "",
                "Column Name": item.column_name if item.column_name is not None else "",
                "Message": item.message,
            }
        )

        if item.details is not None and any(isinstance(v, list) for v in item.details.values()):
            if total_detail_rows >= MAX_ROWS:
                truncated = True
                continue

            try:
                safe_details: dict[str, Any] = {}
                for k, v in item.details.items():
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

                if item.rule not in rule_detail_dfs:
                    rule_detail_dfs[item.rule] = []

                rule_detail_dfs[item.rule].append(df)
                total_detail_rows += len(df)
            except Exception as e:
                try:
                    # some dicts cant be converted into dataframe so just store it as a string
                    df = pl.DataFrame({"details": repr(item.details)})
                    if item.rule not in rule_detail_dfs:
                        rule_detail_dfs[item.rule] = []

                    rule_detail_dfs[item.rule].append(df)
                    total_detail_rows += len(df)

                except Exception as ex:
                    logger.warning(
                        f"Failed to expand details for rule '{item.rule}' into DataFrame"
                        + f" — skipping. Error: {e}, {ex}",
                    )

    if truncated:
        summary_rows.insert(
            0,
            {
                "Severity": "WARNING",
                "Rule": "Export Truncated",
                "Sheet Name": "",
                "Column Name": "",
                "Message": "The dataset generated too many errors. Detailed findings have been"
                + f" truncated to the first {MAX_ROWS} rows to prevent memory exhaustion.",
            },
        )

    df_summary = pl.DataFrame(summary_rows)

    with xlsxwriter.Workbook(str(output_path)) as workbook:
        # Format for header
        header_format = workbook.add_format(
            {"bold": True, "text_wrap": True, "valign": "top", "bg_color": "#D3D3D3", "border": 1}
        )

        _ = df_summary.write_excel(
            workbook=workbook,
            worksheet="Validation Summary",
            header_format=header_format,
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

                _ = df_details.write_excel(
                    workbook=workbook,
                    worksheet=final_sheet_name,
                    header_format=header_format,
                    autofit=True,
                )
        else:
            df_details = pl.DataFrame({"Notice": ["No detailed row-level findings generated."]})
            _ = df_details.write_excel(
                workbook=workbook,
                worksheet="Detailed Findings",
                header_format=header_format,
                autofit=True,
            )
