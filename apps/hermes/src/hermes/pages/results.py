"""Per-validator findings with severity/rule filters, search, and CSV export."""

import io
import re

import polars as pl
import streamlit as st
from argus.orchestrator.output_models import ValidatorResponse
from argus.validators.base import SeverityLevel, ValidationResult

from hermes.common import (
    FOCUS_RULE_KEY,
    SEVERITY_ICON,
    SEVERITY_ORDER,
    build_item_frame,
    detail_column_config,
    iter_validator_items,
    load_session_results,
    render_rule_help,
)

st.title("Results Details")

stored_results = load_session_results()
if stored_results is None:
    st.info("No validation results yet. Validate a dataset on the main page first.")
    st.stop()

# --- findings: one per validator, results grouped by their own severity -----------


def group_results_by_severity(
    results: list[ValidationResult],
) -> list[tuple[SeverityLevel, list[ValidationResult]]]:
    """Group one validator's results by severity, in first-seen order."""
    groups: dict[SeverityLevel, list[ValidationResult]] = {}
    for result in results:
        groups.setdefault(result.severity, []).append(result)
    return list(groups.items())


findings = list(iter_validator_items(stored_results))

if not findings:
    st.success("The validation produced no results to display.")
    st.stop()

total_rows = sum(
    result.get_details_length() for _bucket, validator in findings for result in validator.details
)
st.caption(
    f"{len(findings)} finding(s), {total_rows} detail row(s) in total. "
    "Each section is one validator finding: its messages and detail rows "
    "are inside."
)

# --- filters ----------------------------------------------------------------------

present_severities = {
    result.severity for _bucket, validator in findings for result in validator.details
} | {bucket for bucket, validator in findings if not validator.details}
rule_options = sorted({validator.name for _bucket, validator in findings})
severity_rank = {
    severity: index
    for index, severity in enumerate(SEVERITY_ORDER)
    if severity in present_severities
}

# rule pre-selected on the summary page (consumed once)
default_severity = [
    severity for severity in severity_rank if severity not in ("passed", "admin_info", "info")
]

FILTER_WIDGET_KEYS = ("severity_filter", "rules_filter", "search_filter")


def _restore_filter_state() -> None:
    """Re-seed widget keys from their saved copies.

    Widget state is discarded when a widget is not rendered (e.g. while on
    another page), so restore the last saved selection before the widgets
    are created. Does nothing when the widget state is still alive.
    """
    for widget_key in FILTER_WIDGET_KEYS:
        saved_key = f"{widget_key}_saved"
        if widget_key not in st.session_state and saved_key in st.session_state:
            st.session_state[widget_key] = st.session_state[saved_key]


def _save_filter_state(widget_key: str) -> None:
    """Copy the widget's current selection to a plain session-state key."""
    st.session_state[f"{widget_key}_saved"] = st.session_state[widget_key]


_restore_filter_state()

pending_rule = st.session_state.pop(FOCUS_RULE_KEY, None)
if pending_rule is not None and pending_rule in rule_options:
    st.session_state["rules_filter"] = [pending_rule]

severities = st.multiselect(
    "Severities",
    options=list(severity_rank),
    default=default_severity,
    key="severity_filter",
    on_change=_save_filter_state,
    args=("severity_filter",),
)
rules = st.multiselect(
    "Rules",
    options=rule_options,
    default=[],
    key="rules_filter",
    on_change=_save_filter_state,
    args=("rules_filter",),
)
search = st.text_input(
    "Search messages and detail values",
    placeholder="e.g. column name…",
    key="search_filter",
    on_change=_save_filter_state,
    args=("search_filter",),
)

allowed_severities = set(severities)
allowed_rules = set(rules) if rules else None
pattern = f"(?i){re.escape(search)}" if search else None


def frame_contains(frame: pl.DataFrame, regex: str) -> bool:
    """True when any cell in the frame matches the regex."""
    match_mask = pl.lit(False)
    for column in frame.columns:
        match_mask = match_mask | pl.col(column).cast(pl.String).fill_null("").str.contains(regex)
    return frame.filter(match_mask).height > 0


def result_matches(result: ValidationResult, regex: str) -> bool:
    """True when the result's message or any detail cell matches the regex."""
    if re.search(regex, result.message):
        return True
    frame = build_item_frame(result)
    return frame is not None and frame_contains(frame, regex)


# --- visible validators, in severity-bucket order ------------------------------------

visible: list[tuple[ValidatorResponse, list[tuple[SeverityLevel, list[ValidationResult]]]]] = []
for bucket_severity, validator in findings:
    if allowed_rules is not None and validator.name not in allowed_rules:
        continue
    groups = (
        group_results_by_severity(validator.details)
        if validator.details
        else [(bucket_severity, [])]
    )
    name_match = bool(re.search(pattern, validator.name)) if pattern else False
    kept_groups = []
    for severity, results in groups:
        if allowed_severities and severity not in allowed_severities:
            continue
        if (
            pattern
            and not name_match
            and not any(result_matches(result, pattern) for result in results)
        ):
            continue
        kept_groups.append((severity, results))

    if kept_groups:
        kept_groups.sort(key=lambda group: SEVERITY_ORDER.index(group[0]))
        visible.append((validator, kept_groups))

st.markdown(f"**{len(visible)}** finding(s) match the current filters.")

# --- one expander per validator, messages labelled with their severity ---------------

for validator, kept_groups in visible:
    severity_summary = " · ".join(
        f"{SEVERITY_ICON[severity]} ({len(results)})" if results else SEVERITY_ICON[severity]
        for severity, results in kept_groups
    )
    with st.expander(f"{validator.name} -- {severity_summary}"):
        render_rule_help(validator.name)
        if not any(results for _severity, results in kept_groups):
            st.caption(
                f"This validator reported `{validator.result.name}`; it has no row-level findings."
            )
            continue
        for severity, results in kept_groups:
            for result in results:
                st.markdown(f"**{SEVERITY_ICON[severity]}** — {result.message}")
                location = " · ".join(
                    part for part in (result.sheet_name, result.column_name) if part
                )
                if location:
                    st.caption(location)
                frame = build_item_frame(result)
                if frame is None:
                    st.caption(
                        "This result has no further details; the message above is the whole story."
                    )
                else:
                    st.dataframe(
                        frame,
                        width="stretch",
                        hide_index=True,
                        column_config=detail_column_config(frame),
                    )

# --- export ---------------------------------------------------------------------

if visible:
    export_frames: list[pl.DataFrame] = []
    for validator, kept_groups in visible:
        if not any(results for _severity, results in kept_groups):
            export_frames.append(
                pl.DataFrame(
                    {
                        "rule": [validator.name],
                        "severity": [kept_groups[0][0]],
                        "validator_result": [str(validator.result)],
                    }
                )
            )
            continue
        for severity, results in kept_groups:
            for result in results:
                identity = pl.DataFrame(
                    {
                        "rule": [validator.name],
                        "severity": [severity],
                        "validator_result": [str(validator.result)],
                    }
                ).with_columns(
                    pl.lit(result.message).alias("message"),
                    pl.lit(result.sheet_name or "").alias("sheet_name"),
                    pl.lit(result.column_name or "").alias("column_name"),
                )
                frame = build_item_frame(result)
                export_frames.append(
                    identity.join(frame, how="cross") if frame is not None else identity
                )
    export_frame = pl.concat(export_frames, how="diagonal")

    csv_buffer = io.BytesIO()
    export_frame.write_csv(csv_buffer)
    st.download_button(
        "Download filtered results (CSV)",
        data=csv_buffer.getvalue(),
        file_name="jive_validation_results.csv",
        mime="text/csv",
    )
