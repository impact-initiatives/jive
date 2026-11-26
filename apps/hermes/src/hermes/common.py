"""Shared helpers for the JIVE validation pages.

Single source of truth for the session-state keys, the severity constants,
the Polars frames consolidated from the validated ``PipelineResponse``, and
the summary page rendering.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from datetime import datetime
from functools import cache
from importlib import resources
from typing import Any

import polars as pl
import streamlit as st
from argus.orchestrator.output_models import PipelineResponse, ValidatorResponse
from argus.validators.base import SeverityLevel, ValidationResult, ValidatorResult

from .config import get_settings

# --- session state, navigation and configuration -------------------------------

settings = get_settings()

_RULES_DIR = resources.files("argus") / "../docs" / "validators"

SESSION_KEY = "validation_results"

#: Written on the summary page when a rule is selected; read and popped by
#: the results page to pre-filter the rules widget.
FOCUS_RULE_KEY = "results_focus_rule"

#: Path of the results page, opened by the drill-down buttons on the summary page.
RESULTS_PAGE = "pages/results.py"


def load_session_results() -> PipelineResponse | None:
    """The validated results stored by the validation page, or None."""
    return st.session_state.get(SESSION_KEY)


# --- severity model --------------------------------------------------------------

SEVERITY_ORDER: list[SeverityLevel] = [
    SeverityLevel.ADMIN_ERROR,
    SeverityLevel.ERROR,
    SeverityLevel.WARNING,
    SeverityLevel.INFO,
    SeverityLevel.ADMIN_INFO,
    SeverityLevel.PASSED,
]

ACTIONABLE: list[SeverityLevel] = [
    SeverityLevel.ERROR,
    SeverityLevel.ADMIN_ERROR,
    SeverityLevel.WARNING,
]

SEVERITY_ICON: dict[SeverityLevel, str] = {
    SeverityLevel.ERROR: "❌ Error",
    SeverityLevel.ADMIN_ERROR: "🔥 Admin Error",
    SeverityLevel.WARNING: "⚠️ Warning",
    SeverityLevel.INFO: "ℹ️ Info",
    SeverityLevel.PASSED: "✅ Passed",
}

#: Validator-level outcomes that get their own section on the summary page.
VALIDATOR_FAILURE_RESULTS: frozenset[ValidatorResult] = frozenset(
    {
        ValidatorResult.MISSING_COMPONENTS,
        ValidatorResult.ORCHESTRATOR_ERROR,
    }
)

#: (severity, PipelineResponse attribute) pairs covering every result bucket.
_RESULT_BUCKETS: list[tuple[SeverityLevel, str]] = [
    (SeverityLevel.ADMIN_ERROR, "admin_errors"),
    (SeverityLevel.ERROR, "errors"),
    (SeverityLevel.WARNING, "warnings"),
    (SeverityLevel.INFO, "info"),
    (SeverityLevel.ADMIN_INFO, "admin_info"),
    (SeverityLevel.PASSED, "passed"),
]


# --- iteration over validators and results --------------------------------------


def iter_validator_items(
    response: PipelineResponse,
) -> Generator[tuple[SeverityLevel, ValidatorResponse]]:
    """Yield ``(severity, validator)`` for every validator, in severity order."""
    for severity, attribute in _RESULT_BUCKETS:
        for validator in getattr(response, attribute):
            yield severity, validator


def iter_result_items(
    response: PipelineResponse,
) -> Generator[tuple[SeverityLevel, ValidatorResponse, ValidationResult]]:
    """Yield ``(severity, validator, result)`` per ValidationResult."""
    for _bucket, validator in iter_validator_items(response):
        for result in validator.details:
            yield result.severity, validator, result


def validator_messages(validator: ValidatorResponse) -> list[str]:
    """Deduplicated, order-preserving messages across a validator's results."""
    unique: list[str] = []
    for result in validator.details:
        if result.message and result.message not in unique:
            unique.append(result.message)
    return unique


def validator_messages_for(
    results: PipelineResponse, severity: SeverityLevel, rule_name: str
) -> list[str]:
    """Deduplicated, order-preserving messages of one rule at one severity.

    Falls back to validator-level messages when the validator produced no
    row-level results.
    """
    unique: list[str] = []
    for result_severity, validator in iter_validator_items(results):
        if result_severity != severity or validator.name != rule_name:
            continue
        if not validator.details:
            candidates = validator_messages(validator)
        else:
            candidates = [result.message for result in validator.details]
        for message in candidates:
            if message and message not in unique:
                unique.append(message)
    return unique


# --- rule documentation popovers -------------------------------------------------


@cache
def _load_rule_doc(rule_name: str) -> str | None:
    try:
        return (_RULES_DIR / f"{rule_name}.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def render_rule_help(rule_name: str) -> None:
    """'About this rule' popover for one rule; silently absent when undocumented."""
    doc = _load_rule_doc(rule_name)
    if doc is None:
        return
    with st.popover("ℹ️ About this rule"):
        st.markdown(doc)


# --- Polars frames consolidated from the results ---------------------------------

VALIDATOR_SCHEMA = {
    "severity": pl.String,
    "rule": pl.String,
    "result": pl.String,
    "failed_checks": pl.Int64,
    "issues": pl.Int64,
    "messages": pl.String,
}


def build_validators_frame(response: PipelineResponse) -> pl.DataFrame:
    """One row per validator, keyed by severity and rule.

    Validators without row-level results still get one row: the validator
    outcome itself counts as one failed check producing one issue.
    """
    rows = [
        {
            "severity": severity.value,
            "rule": validator.name,
            "result": str(validator.result),
            "failed_checks": len(validator.details) or 1,
            "issues": sum(result.get_details_length() for result in validator.details) or 1,
            "messages": "\n".join(validator_messages(validator)),
        }
        for severity, validator in iter_validator_items(response)
    ]
    return pl.DataFrame(rows, schema=VALIDATOR_SCHEMA).with_columns(
        pl.col("severity").cast(pl.Enum([severity.value for severity in SEVERITY_ORDER]))
    )


def build_item_frame(item: ValidationResult) -> pl.DataFrame | None:
    """Expand one ValidationResult's details into a detail frame (or None)."""
    columns = _expand_details(item.details)
    if not columns:
        return None
    frame = pl.DataFrame(_pad_columns(columns)).with_columns(pl.all().cast(pl.String))
    return _drop_empty_columns(frame)


def _expand_details(details: dict[str, Any] | None) -> dict[str, list[str]]:
    """Expand one item's details into columns of string lists.

    List values explode to one element per row; scalar values become a
    single row under their key. Columns are padded to a common height
    afterwards by :func:`_pad_columns`.
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


def _drop_empty_columns(frame: pl.DataFrame) -> pl.DataFrame:
    """Drop columns whose every value is null or blank."""
    keep = [
        name
        for name in frame.columns
        if frame[name].null_count() + frame[name].eq("").sum() != frame.height
    ]
    return frame.select(keep) if keep else frame


# --- column configuration ----------------------------------------------------------
#
# Wide text columns make st.dataframe's built-in cell expansion (hover →
# expand icon) reveal the full text of long cells.


def detail_column_config(frame: pl.DataFrame) -> dict:
    """Wide text columns for a finding's detail frame."""
    return {name: st.column_config.TextColumn(name, width="large") for name in frame.columns}


def issue_summary_column_config() -> dict:
    """Column configuration for the severity × rule roll-up table."""
    return {
        "rule": st.column_config.TextColumn("Rule", width="large"),
        "severity_label": st.column_config.TextColumn("Severity"),
        "failed_checks": st.column_config.NumberColumn("Failed Checks"),
        "issues_found": st.column_config.NumberColumn("Issues Found"),
    }


# --- shared rendering helpers -------------------------------------------------------


def render_messages(messages: list[str], empty_caption: str) -> None:
    """One message as a paragraph, several as a bullet list, none as a caption."""
    if not messages:
        st.caption(empty_caption)
    elif len(messages) == 1:
        st.markdown(messages[0])
    else:
        st.markdown("\n".join(f"- {message}" for message in messages))


def render_drilldown_card(
    heading: str,
    rule_name: str,
    button_key: str,
    messages: list[str],
    empty_caption: str,
) -> None:
    """Bordered card with a heading, the rule's help popover, and a button that
    opens the results page filtered to the rule."""
    with st.container(border=True):
        heading_column, help_column, link_column = st.columns(
            [4, 1, 1.5], vertical_alignment="center"
        )
        heading_column.markdown(heading)
        with help_column:
            render_rule_help(rule_name)
        with link_column:
            if st.button("View details →", key=button_key, use_container_width=True):
                st.session_state[FOCUS_RULE_KEY] = rule_name
                st.switch_page(RESULTS_PAGE)
        render_messages(messages, empty_caption)


# --- summary-page sections ----------------------------------------------------------


def render_validator_failures(results: PipelineResponse) -> None:
    """One bordered card per validator reported as MISSING_COMPONENTS or
    ORCHESTRATOR_ERROR, in severity order."""
    failures = [
        (severity, validator)
        for severity, validator in iter_validator_items(results)
        if validator.result in VALIDATOR_FAILURE_RESULTS
    ]
    if not failures:
        return

    failures.sort(key=lambda failure: SEVERITY_ORDER.index(failure[0]))
    st.subheader("Critical Issues")
    st.text(f"These {len(failures)} issues can prevent validation rules from running.")

    for severity, validator in failures:
        icon = SEVERITY_ICON.get(severity, "")
        heading = f"**{icon} · {validator.name}** — reported `{validator.result.name}`"
        render_drilldown_card(
            heading,
            validator.name,
            f"failure_details_{severity}_{validator.name}",
            validator_messages(validator),
            "No validator-level messages were recorded.",
        )


def render_issue_summary(results: PipelineResponse) -> None:
    """Severity × rule roll-up table with row selection and drill-down."""
    frame = build_validators_frame(results).filter(
        pl.col("severity").is_in([severity.value for severity in ACTIONABLE])
    )
    if frame.height == 0:
        return

    st.subheader("Summary of validation issues")

    rollup = (
        frame.group_by("rule", "severity")
        .agg(
            pl.col("failed_checks").sum().alias("failed_checks"),
            pl.col("issues").sum().alias("issues_found"),
        )
        .with_columns(pl.col("severity").cast(pl.Enum([severity.value for severity in ACTIONABLE])))
        .sort("severity", "rule")
    )
    display_frame = (
        rollup.with_columns(
            pl.col("severity")
            .cast(pl.String)
            .replace_strict(
                {severity.value: icon for severity, icon in SEVERITY_ICON.items()}, default=""
            )
            .alias("severity_label")
        )
        .select(["rule", "severity_label", "failed_checks", "issues_found", "severity"])
        .with_row_index("_row")
    )

    selection = st.dataframe(
        display_frame.drop("_row", "severity"),
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

    picked = display_frame.row(int(selected_rows[0]), named=True)
    severity = SeverityLevel(picked["severity"])
    icon = SEVERITY_ICON.get(severity, "")
    heading = (
        f"**{icon} · {picked['rule']}** — {picked['failed_checks']} failed check(s), "
        f"{picked['issues_found']} issue(s)"
    )
    render_drilldown_card(
        heading,
        picked["rule"],
        "issue_summary_drilldown",
        validator_messages_for(results, severity, picked["rule"]),
        "This rule produced no row-level messages.",
    )


def render_summary(results: PipelineResponse) -> None:
    """Render the full results summary: status banner, context line, KPI strip,
    validator-failure section, per-rule roll-up, and passed-checks paragraph."""
    # --- status banner --------------------------------------------------------
    if results.success:
        st.success("✅ **JIVE VALIDATION PASSED**")
    else:
        st.error("❌ **JIVE VALIDATION FAILED**")

    # --- context line -----------------------------------------------------------
    metadata = results.metadata
    validated_at = ""
    if metadata.validation_date:
        with contextlib.suppress(ValueError):
            validated_at = datetime.fromisoformat(metadata.validation_date).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

    st.caption(
        f"File: **{metadata.file_name}** · "
        f"Programme: **{metadata.programme_type}** · "
        f"Output: **{metadata.output_type}** · "
        f"Validated: {validated_at}"
    )

    # --- rules grouped by outcome ----------------------------------------------
    rules_by_severity: dict[SeverityLevel, set[str]] = {}
    for severity, validator in iter_validator_items(results):
        rules_by_severity.setdefault(severity, set()).add(validator.name)

    actionable_rules: set[str] = set()
    for severity in ACTIONABLE:
        actionable_rules.update(rules_by_severity.get(severity, set()))

    passed_rules = sorted(rules_by_severity.get(SeverityLevel.PASSED, set()) - actionable_rules)

    # --- KPI strip --------------------------------------------------------------
    kpi_order = [
        SeverityLevel.ADMIN_ERROR,
        SeverityLevel.ERROR,
        SeverityLevel.WARNING,
        SeverityLevel.PASSED,
    ]
    metric_values = {
        severity.value: len(rules_by_severity.get(severity, set()))
        for severity in kpi_order
        if severity is not SeverityLevel.PASSED
    }
    metric_values[SeverityLevel.PASSED.value] = len(passed_rules)
    metric_columns = st.columns(len(kpi_order))
    for column, severity in zip(metric_columns, kpi_order, strict=False):
        column.metric(
            label=severity.value.replace("_", " ").title(),
            value=f"{metric_values[severity.value]:,}",
        )

    # --- failing validators and issue roll-up ------------------------------------
    render_validator_failures(results)
    render_issue_summary(results)

    # --- passed checks -------------------------------------------------------------
    if passed_rules:
        st.markdown(
            f"*{len(passed_rules)} core quality checks passed successfully ✅ "
            f"({', '.join(passed_rules)}).*"
        )
    else:
        st.markdown("*No core checks passed.*")

    # --- footer ---------------------------------------------------------------------
    st.divider()
    st.markdown(f"Version: {settings.jive_version}")
