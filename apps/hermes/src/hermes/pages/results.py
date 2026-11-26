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
    ValidationData,
    detail_column_config,
    get_item_frame,
    get_validator_items,
    load_session_results,
    render_rule_help,
)

st.title("Results Details")

stored: ValidationData | None = load_session_results()
if stored is None:
    st.info("No validation results yet. Validate a dataset on the main page first.")
    st.stop()

# --- findings: one per validator, results grouped by their own severity


validator_responses = list(get_validator_items(stored.response))
if not validator_responses:
    st.success("The validation process produced no results to display.")
    st.stop()

total_rows = sum(
    result.get_details_length()
    for _, validator in validator_responses
    for result in validator.details
)
st.caption(
    f"{len(validator_responses)} result(s), {total_rows} detail row(s) in total. "
    "Each section is one validator response: its messages and detail rows "
    "are inside."
)

#  page filters

present_severities = {
    result.severity for _, validator in validator_responses for result in validator.details
} | {bucket for bucket, validator in validator_responses if not validator.details}
rule_options = sorted({validator.name for _bucket, validator in validator_responses})
severity_rank = {
    severity: index
    for index, severity in enumerate(SEVERITY_ORDER)
    if severity in present_severities
}

# default severities for filtering
default_severity = [
    severity for severity in severity_rank if severity not in ("passed", "admin_info", "info")
]

FILTER_WIDGET_KEYS = ("severity_filter", "rules_filter", "search_filter")

# gets saved filters to maintain filters when chaning pages
for widget_key in FILTER_WIDGET_KEYS:
    saved_key = f"{widget_key}_saved"
    if widget_key not in st.session_state and saved_key in st.session_state:
        st.session_state[widget_key] = st.session_state[saved_key]


def _save_filter_state(widget_key: str) -> None:
    """Copy the widget's current selection to a plain session-state key."""
    st.session_state[f"{widget_key}_saved"] = st.session_state[widget_key]


# rule selected from summary page
pending_rule = st.session_state.pop(FOCUS_RULE_KEY, None)
if pending_rule is not None and pending_rule in rule_options:
    st.session_state["rules_filter"] = [pending_rule]

# page filters
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

filtered_severities = set(severities)
filtered_rules = set(rules) if rules else None
filter_search_pattern = f"(?i){re.escape(search)}" if search else None


def frame_contains(frame: pl.DataFrame, regex: str) -> bool:
    """Searches a dataframe for a regex pattern"""
    match_mask = pl.lit(False)
    for column in frame.columns:
        match_mask = match_mask | pl.col(column).cast(pl.String).fill_null("").str.contains(regex)
    return frame.filter(match_mask).height > 0


def result_matches(validator: ValidatorResponse, result: ValidationResult, regex: str) -> bool:
    """Searches the results message and cell values. If a match is found it
    returns true."""
    if re.search(regex, result.message):
        return True
    frame = get_item_frame(stored, validator, result)
    return frame is not None and frame_contains(frame, regex)


#  visible validators, in severity order

visible_validator_responses: list[
    tuple[ValidatorResponse, list[tuple[SeverityLevel, list[ValidationResult]]]]
] = []
for bucket_severity, validator in validator_responses:
    if filtered_rules is not None and validator.name not in filtered_rules:
        continue

    # Group one validator's results by severity
    validator_response_groups: list[tuple[SeverityLevel, list[ValidationResult]]] = []
    group: dict[SeverityLevel, list[ValidationResult]] = {}
    if validator.details:
        for result in validator.details:
            group.setdefault(result.severity, []).append(result)
        validator_response_groups = list(group.items())
    else:
        validator_response_groups = [(bucket_severity, [])]

    name_match = (
        bool(re.search(filter_search_pattern, validator.name)) if filter_search_pattern else False
    )

    # filter the responses based on the filters
    filtered_validator_response_groups = []
    for severity, results in validator_response_groups:
        if filtered_severities and severity not in filtered_severities:
            continue
        if (
            filter_search_pattern
            and not name_match
            and not any(
                result_matches(validator, result, filter_search_pattern) for result in results
            )
        ):
            continue
        filtered_validator_response_groups.append((severity, results))

    # sort the responses
    if filtered_validator_response_groups:
        filtered_validator_response_groups.sort(key=lambda group: SEVERITY_ORDER.index(group[0]))
        visible_validator_responses.append((validator, filtered_validator_response_groups))

st.markdown(f"**{len(visible_validator_responses)}** finding(s) match the current filters.")

# Display the results. one expander per validator, messages labelled with their severity

for validator, filtered_validator_response_groups in visible_validator_responses:
    # parent validator
    severity_summary = " · ".join(
        f"{SEVERITY_ICON[severity]} ({len(results)})" if results else SEVERITY_ICON[severity]
        for severity, results in filtered_validator_response_groups
    )
    with st.expander(f"{validator.name} -- {severity_summary}"):
        render_rule_help(validator.name)
        if not any(results for _severity, results in filtered_validator_response_groups):
            st.caption(
                f"This validator reported `{validator.result.name}`; it has no row-level findings."
            )
            continue
        for severity, results in filtered_validator_response_groups:
            # for each severity grouping in the parent
            for result in results:
                # for each result in the severity grouping
                st.markdown(f"**{SEVERITY_ICON[severity]}** — {result.message}")

                result_details_df = get_item_frame(stored, validator, result)
                if result_details_df is None:
                    st.caption("This result has no further details.")
                else:
                    st.dataframe(
                        result_details_df,
                        width="stretch",
                        hide_index=True,
                        column_config=detail_column_config(result_details_df),
                    )

#  export results

if visible_validator_responses:
    export_frames: list[pl.DataFrame] = []
    for validator, filtered_validator_response_groups in visible_validator_responses:
        if not any(results for _severity, results in filtered_validator_response_groups):
            export_frames.append(
                pl.DataFrame(
                    {
                        "rule": [validator.name],
                        "severity": [filtered_validator_response_groups[0][0]],
                        "validator_result": [str(validator.result)],
                    }
                )
            )
            continue
        for severity, results in filtered_validator_response_groups:
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
                result_details_df = get_item_frame(stored, validator, result)
                export_frames.append(
                    identity.join(result_details_df, how="cross")
                    if result_details_df is not None
                    else identity
                )
    export_frame = pl.concat(export_frames, how="diagonal")

    csv_buffer = io.BytesIO()
    export_frame.write_csv(csv_buffer)
    st.download_button(
        "Download filtered results (CSV)",
        data=csv_buffer.getvalue(),
        file_name="hermes_validation_results.csv",
        mime="text/csv",
    )
