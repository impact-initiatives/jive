import io
import re

import polars as pl
import streamlit as st
from argus.orchestrator.output_models import ValidatorResponse

from hermes.common import (
    FOCUS_RULE_KEY,
    SESSION_KEY,
    SEVERITY_ICON,
    SEVERITY_ORDER,
    as_pipeline_response,
    build_item_frame,
    detail_column_config,
    iter_validator_items,
    render_rule_help,
)

st.title("Results Details")

if SESSION_KEY not in st.session_state or st.session_state[SESSION_KEY] is None:
    st.info("No validation results yet. Validate a dataset on the main page first.")
    st.stop()

results = as_pipeline_response(st.session_state[SESSION_KEY])

# --- all findings, in severity order -----------------------------------------
# One finding per ValidatorResponse: the validator is the "rule", and its
# ValidationResult list is expanded inside the expander.
findings = [(severity, validator) for severity, validator in iter_validator_items(results)]

if not findings:
    st.success("The validation produced no results to display.")
    st.stop()

total_rows = sum(
    result.get_details_length() for _sev, validator in findings for result in validator.details
)
st.caption(
    f"{len(findings)} finding(s), {total_rows} detail row(s) in total. "
    "Each section is one validator finding: its messages and detail rows "
    "are inside."
)

# --- filters ------------------------------------------------------------------
severity_rank = {sev: i for i, sev in enumerate(SEVERITY_ORDER)}

severity_options = [sev for sev in SEVERITY_ORDER if any(sev == s for s, _v in findings)]
rule_options = sorted({validator.name for _s, validator in findings})

# rule pre-selected on the summary page (consumed once)
pending_rule = st.session_state.pop(FOCUS_RULE_KEY, None)

severities = st.multiselect(
    "Severities",
    options=severity_options,
    default=[s for s in severity_options if s not in ("passed", "admin_info", "info")],
)
rules = st.multiselect(
    "Rules",
    options=rule_options,
    default=[pending_rule] if pending_rule in rule_options else [],
)
search = st.text_input("Search messages and detail values", placeholder="e.g. column name…")

# --- resolve visible findings ---------------------------------------------------
allowed_severities = set(severities)
allowed_rules = set(rules) if rules else None

pattern = f"(?i){re.escape(search)}" if search else None


def frame_contains(frame: pl.DataFrame, regex: str) -> bool:
    """True when any cell in the frame matches the regex."""
    mask = pl.lit(False)
    for column in frame.columns:
        mask = mask | pl.col(column).cast(pl.String).fill_null("").str.contains(regex)
    return frame.filter(mask).height > 0


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


visible: list[tuple[int, str, ValidatorResponse]] = []
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

# --- one expander per validator finding -----------------------------------------
for _rank, severity, validator in visible:
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

# --- export ------------------------------------------------------------------
if visible:
    export_frames: list[pl.DataFrame] = []
    for _rank, severity, validator in visible:
        base = pl.DataFrame(
            {
                "rule": [validator.name],
                "severity": [severity],
                "validator_result": [str(validator.result)],
            }
        )
        if not validator.details:
            export_frames.append(base)
            continue
        for result in validator.details:
            row = base.with_columns(
                pl.lit(result.message).alias("message"),
                pl.lit(result.sheet_name or "").alias("sheet_name"),
                pl.lit(result.column_name or "").alias("column_name"),
            )
            frame = build_item_frame(result)
            # repeat the finding's identity across each detail row
            export_frames.append(row.join(frame, how="cross") if frame is not None else row)
    export_df = pl.concat(export_frames, how="diagonal")

    csv_buffer = io.BytesIO()
    export_df.write_csv(csv_buffer)
    st.download_button(
        "Download filtered results (CSV)",
        data=csv_buffer.getvalue(),
        file_name="jive_validation_results.csv",
        mime="text/csv",
    )
