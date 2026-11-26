"""Per-validator findings with severity/rule filters, search, and CSV export."""

import io
import re

import polars as pl
import streamlit as st
from argus.orchestrator.output_models import ValidatorResponse
from argus.validators.base import SeverityLevel

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

# --- all findings, in severity order --------------------------------------------
# One finding per ValidatorResponse: the validator is the "rule", and its
# ValidationResult list is expanded inside the expander.
findings = [(severity, validator) for severity, validator in iter_validator_items(stored_results)]

if not findings:
    st.success("The validation produced no results to display.")
    st.stop()

total_rows = sum(
    result.get_details_length() for _severity, validator in findings for result in validator.details
)
st.caption(
    f"{len(findings)} finding(s), {total_rows} detail row(s) in total. "
    "Each section is one validator finding: its messages and detail rows "
    "are inside."
)

# --- filters ----------------------------------------------------------------------

present_severities = {severity for severity, _validator in findings}
rule_options = sorted({validator.name for _severity, validator in findings})
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


def validator_matches(validator: ValidatorResponse, regex: str | None) -> bool:
    """True when the validator name, any message or any detail cell matches."""
    if regex is None:
        return True
    if re.search(regex, validator.name):
        return True
    for result in validator.details:
        if re.search(regex, result.message):
            return True
        frame = build_item_frame(result)
        if frame is not None and frame_contains(frame, regex):
            return True
    return False


# --- visible findings, sorted by severity ----------------------------------------

visible: list[tuple[int, SeverityLevel, ValidatorResponse]] = []
for severity, validator in findings:
    if allowed_severities and severity not in allowed_severities:
        continue
    if allowed_rules is not None and validator.name not in allowed_rules:
        continue
    if not validator_matches(validator, pattern):
        continue
    visible.append((severity_rank.get(severity, len(SEVERITY_ORDER)), severity, validator))

visible.sort(key=lambda entry: entry[0])

st.markdown(f"**{len(visible)}** finding(s) match the current filters.")

# --- one expander per validator finding --------------------------------------------

for _order, severity, validator in visible:
    icon = SEVERITY_ICON.get(severity, "")
    with st.expander(f"{icon} · {validator.name}"):
        render_rule_help(validator.name)
        if not validator.details:
            st.caption(
                f"This validator reported `{validator.result.name}`; it has no row-level findings."
            )
            continue
        for result in validator.details:
            st.markdown(f"**{result.message}**")
            location = " · ".join(part for part in (result.sheet_name, result.column_name) if part)
            if location:
                st.caption(location)
            frame = build_item_frame(result)
            if frame is None:
                st.caption(
                    "This finding has no row-level details; the message above is the whole story."
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
    for _order, severity, validator in visible:
        finding_identity = pl.DataFrame(
            {
                "rule": [validator.name],
                "severity": [severity],
                "validator_result": [str(validator.result)],
            }
        )
        if not validator.details:
            export_frames.append(finding_identity)
            continue
        for result in validator.details:
            result_row = finding_identity.with_columns(
                pl.lit(result.message).alias("message"),
                pl.lit(result.sheet_name or "").alias("sheet_name"),
                pl.lit(result.column_name or "").alias("column_name"),
            )
            frame = build_item_frame(result)
            export_frames.append(
                result_row.join(frame, how="cross") if frame is not None else result_row
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
