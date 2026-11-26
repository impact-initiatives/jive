"""Validate a dataset — uploader plus inline results summary on one page."""

import streamlit as st

from hermes.common import (
    RESULTS_PAGE,
    SESSION_KEY,
    load_session_results,
    render_summary,
    run_pipeline,
)

st.title("Validate a Dataset")

# --- upload and run -----------------------------------------------------------
input_column_1, input_column_2 = st.columns(2)
with input_column_1:
    programme_type = st.selectbox(
        "Programme Type",
        ("JMMI", "Other"),
        index=None,
        placeholder="Select a programme type...",
    )

with input_column_2:
    dataset_type = st.selectbox(
        "Dataset Type",
        ("Dataset", "Analysis"),
        index=None,
        placeholder="Select a dataset type...",
    )
uploaded_file = st.file_uploader("Choose a dataset file to validate", type=["xls", "xlsx"])
run_validation = st.button(
    "Run validation",
    type="primary",
    disabled=all([uploaded_file is None or dataset_type is None or programme_type is None]),
)

if (
    run_validation
    and uploaded_file is not None
    and dataset_type is not None
    and programme_type is not None
):
    with st.spinner("Validating…", width="stretch"):
        st.session_state[SESSION_KEY] = run_pipeline(
            uploaded_file.getvalue(), uploaded_file.name, programme_type, dataset_type
        )

# --- summary -------------------------------------------------------------------

stored_results = load_session_results()
if stored_results is not None:
    render_summary(stored_results)
    with st.bottom:
        if st.button("View all result details →", use_container_width=True):
            st.switch_page(RESULTS_PAGE)
else:
    st.info("Upload a file above and run the validation to see the summary here.")
