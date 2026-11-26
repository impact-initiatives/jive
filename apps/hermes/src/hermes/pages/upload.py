"""Validate a dataset — uploader plus inline results summary on one page."""

import streamlit as st
from argus.orchestrator.output_models import PipelineResponse
from argus.orchestrator.validation_pipeline import ValidationPipeline

from hermes.common import SESSION_KEY, load_session_results, render_summary

st.title("Validate a dataset")

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
        results = ValidationPipeline().run_all(uploaded_file, programme_type, dataset_type)
    st.session_state[SESSION_KEY] = PipelineResponse.model_validate(results)

# --- summary -------------------------------------------------------------------

stored_results = load_session_results()
if stored_results is not None:
    render_summary(stored_results)
else:
    st.info("Upload a file above and run the validation to see the summary here.")
