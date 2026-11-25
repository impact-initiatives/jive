from __future__ import annotations

import contextlib
from collections.abc import Generator
from datetime import datetime
from functools import cache
from importlib import resources
from typing import Any

import polars as pl
import streamlit as st
from argus.orchestrator.output_models import (
    PipelineResponse,
    ValidatorResponse,
)
from argus.validators.base import ValidationResult, ValidatorResult

from .config import get_settings

"""Shared helpers for the JIVE results pages.

Single source of truth for severity constants, the validator-level failure
section, and the consolidation of the validated ``PipelineResponse`` into
Polars frames.
"""
settings = get_settings()

_RULES_DIR = resources.files("argus") / "../docs" / "validators"
SESSION_KEY = "validation_results"

#: Written on the summary page when a rule is selected; read and popped by
#: the results page to pre-filter the rules widget.
FOCUS_RULE_KEY = "results_focus_rule"

SEVERITY_ORDER: list[str] = ["error", "admin_error", "warning", "info", "admin_info", "passed"]
ACTIONABLE: list[str] = ["error", "admin_error", "warning"]
SEVERITY_ICON: dict[str, str] = {
    "error": "❌ Error",
    "admin_error": "🔥 Admin Error",
    "warning": "⚠️ Warning",
}

#: Validator-level outcomes that get their own section on the summary page.
VALIDATOR_FAILURE_RESULTS: frozenset[ValidatorResult] = frozenset(
    {
        ValidatorResult.MISSING_COMPONENTS,
        ValidatorResult.ORCHESTRATOR_ERROR,
    }
)

#: (severity label, PipelineResponse attribute) — enumerates every result bucket
_SEVERITY_BUCKETS: list[tuple[str, str]] = [
    ("error", "errors"),
    ("admin_error", "admin_errors"),
    ("warning", "warnings"),
    ("info", "info"),
    ("admin_info", "admin_info"),
    ("passed", "passed"),
]

VALIDATOR_SCHEMA = {
    "severity": pl.String,
    "rule": pl.String,
    "result": pl.String,
    "failed_checks": pl.Int64,
    "issues": pl.Int64,
    "messages": pl.String,
}

#: Path of the results page, used by st.switch_page on the summary page.
RESULTS_PAGE = "pages/results.py"


@cache
def _load_rule_doc(slug: str) -> str | None:
    try:
        return (_RULES_DIR / f"{slug}.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def render_rule_help(rule_name: str) -> None:
    """'About this rule' popover for one rule; silently absent when undocumented."""
    doc = _load_rule_doc(rule_name)
    if doc is None:
        return
    with st.popover("ℹ️ About this rule"):
        st.markdown(doc)


def as_pipeline_response(results: PipelineResponse | dict[str, Any]) -> PipelineResponse:
    """Accept either the validated model or the raw pipeline dict."""
    if isinstance(results, PipelineResponse):
        return results
    return PipelineResponse.model_validate(results)


def iter_validator_items(
    response: PipelineResponse,
) -> Generator[tuple[str, ValidatorResponse]]:
    """Yield ``(severity, validator)`` for every validator, in severity order."""
    for severity, attr in _SEVERITY_BUCKETS:
        for validator in getattr(response, attr):
            yield severity, validator


def validator_messages(validator: ValidatorResponse) -> list[str]:
    """Deduplicated, order-preserving messages across a validator's results."""
    seen: list[str] = []
    for result in validator.details:
        if result.message and result.message not in seen:
            seen.append(result.message)
    return seen


def build_validators_df(response: PipelineResponse) -> pl.DataFrame:
    """One row per validator; ``issues`` sums get_details_length() over its results."""
    rows = [
        {
            "severity": severity,
            "rule": validator.name,
            "result": str(validator.result),
            "failed_checks": len(validator.details),
            "issues": sum(result.get_details_length() for result in validator.details),
            "messages": " | ".join(validator_messages(validator)),
        }
        for severity, validator in iter_validator_items(response)
    ]
    return pl.DataFrame(rows, schema=VALIDATOR_SCHEMA).with_columns(
        pl.col("severity").cast(pl.Enum(SEVERITY_ORDER))
    )


def _drop_empty_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Drop columns whose every value is null or blank."""
    keep = [
        name for name in df.columns if df[name].null_count() + df[name].eq("").sum() != df.height
    ]
    return df.select(keep) if keep else df


def build_item_frame(item: ValidationResult) -> pl.DataFrame | None:
    """Expand one ValidationResult's details into a detail frame (or None)."""
    columns = _expand_details(item.details)
    if not columns:
        return None
    df = pl.DataFrame(_pad_columns(columns)).with_columns(pl.all().cast(pl.String))
    return _drop_empty_columns(df)


def _expand_details(details: dict[str, Any] | None) -> dict[str, list[str]]:
    """Expand one item's details into columns of string lists.

    List values explode to one element per row (like the Excel exporter);
    scalar values become a single row under their key. Columns are padded
    to a common height afterwards.
    """
    columns: dict[str, list[str]] = {}
    if not details:
        return columns
    for key, value in details.items():
        if isinstance(value, list) and value:
            columns[key] = [str(element) if element is not None else "" for element in value]
        else:
            columns[key] = [str(value)]
    return columns


def _pad_columns(columns: dict[str, list[str]]) -> dict[str, list[str]]:
    """Pad all columns to the same height so they can form a DataFrame."""
    height = max(len(values) for values in columns.values())
    return {key: values + [""] * (height - len(values)) for key, values in columns.items()}


# --- column configuration -----------------------------------------------------
#
# st.dataframe truncates long cell text with an ellipsis; ``width="large"``
# makes the columns wide and the built-in cell expansion (hover → expand icon,
# or click) reveals the full text. There is no native wrap-to-height option in
# st.dataframe, so wide text columns + expansion is the closest available
# behaviour to "always show all text".


def detail_column_config(frame: pl.DataFrame) -> dict:
    """Wide text columns for a finding's detail frame."""
    return {name: st.column_config.TextColumn(name, width="large") for name in frame.columns}


def issue_summary_column_config() -> dict:
    return {
        "rule": st.column_config.TextColumn("Rule", width="large"),
        "severity_label": st.column_config.TextColumn("Severity"),
        "failed_checks": st.column_config.NumberColumn("Failed Checks"),
        "issues_found": st.column_config.NumberColumn("Issues Found"),
    }


# --- summary-page sections ----------------------------------------------------


def render_validator_failures(
    results: PipelineResponse, *, results_page: str = RESULTS_PAGE
) -> None:
    """One bordered card per validator whose outcome was ,
    MISSING_COMPONENTS or ORCHESTRATOR_ERROR, with the rule name, messages,
    and a link-button into the filtered results view."""
    failures = [
        (severity, validator)
        for severity, validator in iter_validator_items(results)
        if validator.result in VALIDATOR_FAILURE_RESULTS
    ]
    if not failures:
        return

    failures.sort(key=lambda entry: SEVERITY_ORDER.index(entry[0]))
    st.subheader("Critical Issues")
    st.text("These issues can prevent validation rules from running.")

    for severity, validator in failures:
        icon = SEVERITY_ICON.get(severity, "")
        messages = validator_messages(validator)
        with st.container(border=True):
            header, help_col, link = st.columns([4, 1, 1.5], vertical_alignment="center")
            header.markdown(f"**{icon} · {validator.name}** — reported `{validator.result.name}`")
            with help_col:
                render_rule_help(validator.name)
            with link:
                if st.button(
                    "View details →",
                    key=f"failure_details_{severity}_{validator.name}",
                    use_container_width=True,
                ):
                    st.session_state[FOCUS_RULE_KEY] = validator.name
                    st.switch_page(results_page)

            if not messages:
                st.caption("No validator-level messages were recorded.")
            elif len(messages) == 1:
                st.markdown(messages[0])
            else:
                st.markdown("\n".join(f"- {m}" for m in messages))


def render_issue_summary(
    results: PipelineResponse,
    *,
    results_page: str = RESULTS_PAGE,
) -> None:
    """Severity × rule roll-up table with row selection.

    Selecting a row shows the rule's header, help popover, drill-down button
    and deduplicated messages in one card.
    """
    df = build_validators_df(results).filter(pl.col("severity").is_in(ACTIONABLE))
    if df.height == 0:
        return

    st.subheader("Summary of validation issues")

    rollup = (
        df.group_by("rule", "severity")
        .agg(
            pl.col("failed_checks").sum().alias("failed_checks"),
            pl.col("issues").sum().alias("issues_found"),
        )
        .with_columns(pl.col("severity").cast(pl.Enum(ACTIONABLE)))
        .sort("severity", "rule")
    )
    display_df = (
        rollup.with_columns(
            pl.col("severity")
            .cast(pl.String)
            .replace_strict(SEVERITY_ICON, default="")
            .alias("severity_label")
        )
        .select(["rule", "severity_label", "failed_checks", "issues_found", "severity"])
        .with_row_index("_row")
    )

    selection = st.dataframe(
        display_df.drop("_row", "severity"),
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="issue_summary_selection",
        column_config=issue_summary_column_config(),
    )

    selected_rows = selection.get("selection", {}).get("rows", [])
    if not selected_rows:
        st.caption("Select a row above to see its messages and open the results view.")
        return

    picked = display_df.row(int(selected_rows[0]), named=True)
    severity, rule = picked["severity"], picked["rule"]
    icon = SEVERITY_ICON.get(severity, "")
    message_list = validator_messages_for(results, severity, rule)

    with st.container(border=True):
        header, help_col, link = st.columns([4, 1, 1.5], vertical_alignment="center")
        header.markdown(
            f"**{icon} · {rule}** — {picked['failed_checks']} failed check(s), "
            f"{picked['issues_found']} issue(s)"
        )
        with help_col:
            render_rule_help(rule)
        with link:
            if st.button(
                "View details →",
                key="issue_summary_drilldown",
                use_container_width=True,
            ):
                st.session_state[FOCUS_RULE_KEY] = rule
                st.switch_page(results_page)

        if not message_list:
            st.caption("This rule produced no row-level messages.")
        elif len(message_list):
            if len(message_list) == 1:
                st.markdown(message_list[0])
            else:
                st.markdown("\n".join(f"- {m}" for m in message_list))


def validator_messages_for(results: PipelineResponse, severity: str, rule: str) -> list[str]:
    seen: list[str] = []
    for sev, validator in iter_validator_items(results):
        if sev == severity and validator.name == rule:
            for message in validator_messages(validator):
                if message not in seen:
                    seen.append(message)
    return seen


def render_summary(
    results: PipelineResponse,
    *,
    results_page: str = RESULTS_PAGE,
) -> None:
    """Render the full results summary below whatever the calling page drew first.

    Status banner, context card, KPI strip, validator-failure section,
    per-rule roll-up with drill-down, and the passed-checks paragraph.
    """
    # --- status banner (≈ the coloured ADF panel) --------------------------
    if results.success:
        st.success("✅ **JIVE VALIDATION PASSED**")
    else:
        st.error("❌ **JIVE VALIDATION FAILED**")

    # --- context card (≈ the JSM submission-context panel) ------------------
    md = results.metadata
    valid_at = ""
    if md.validation_date:
        with contextlib.suppress(ValueError):
            valid_at = datetime.fromisoformat(md.validation_date).strftime("%Y-%m-%d %H:%M:%S")

    st.caption(
        f"File: **{md.file_name}** · "
        f"Programme: **{md.programme_type}** · "
        f"Output: **{md.output_type}** · "
        f"Validated: {valid_at}"
    )

    df = build_validators_df(results)

    # --- KPI strip (now one count per validator, not per finding) -----------
    actionable_rules = set(df.filter(pl.col("severity").is_in(ACTIONABLE))["rule"].to_list())

    kpi_order = ["error", "admin_error", "warning", "passed"]
    failed_metrics = {
        row["severity"]: row["failed_checks"]
        for row in df.filter(pl.col("severity").is_in(ACTIONABLE))
        .group_by("severity")
        .agg(pl.col("failed_checks").sum())
        .iter_rows(named=True)
    }
    passed_rule_count = (
        df.filter((pl.col("severity") == "passed") & (~pl.col("rule").is_in(actionable_rules)))
        .get_column("rule")
        .n_unique()
    )

    metrics = {**failed_metrics, "passed": passed_rule_count}
    cols = st.columns(len(kpi_order))
    for col, sev in zip(cols, kpi_order, strict=False):
        col.metric(
            label=sev.replace(
                "_",
                " ",
            ).title(),
            value=f"{metrics.get(sev, 0):,}",
        )

    # --- validators that failed to run --------------------------------------
    render_validator_failures(results, results_page=results_page)

    # --- roll-up with drill-down to the results page -------------------------
    render_issue_summary(results, results_page=results_page)

    # --- passed checks (≈ the italic passed-rules paragraph) ----------------
    actionable_rules = set(df.filter(pl.col("severity").is_in(ACTIONABLE))["rule"].to_list())
    passed_rules = sorted(
        set(
            df.filter((pl.col("severity") == "passed") & (~pl.col("rule").is_in(actionable_rules)))[
                "rule"
            ].to_list()
        )
    )
    if passed_rules:
        st.markdown(
            f"*{len(passed_rules)} core quality checks passed successfully ✅ "
            f"({', '.join(passed_rules)}).*"
        )
    else:
        st.markdown("*No core checks passed.*")

    # --- footer (≈ the version/stat rule) ------------------------------------
    st.divider()
    st.markdown(f"Version: {settings.jive_version}")
