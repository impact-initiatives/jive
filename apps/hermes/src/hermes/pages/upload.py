# pages/validation.py
"""Validate a dataset — uploader plus inline results summary on one page."""

import streamlit as st
from argus.orchestrator.validation_pipeline import ValidationPipeline

from hermes.common import (
    RESULTS_PAGE,
    SESSION_KEY,
    PipelineResponse,
    as_pipeline_response,
    render_summary,
)

st.title("Validate a dataset")

uploaded_file = st.file_uploader("Choose a dataset file to validate", type=["xls", "xlsx"])
run_validation = st.button("Run validation", type="primary", disabled=uploaded_file is None)

if run_validation and uploaded_file is not None:
    with st.spinner("Validating…"):
        results = ValidationPipeline().run_all(uploaded_file, "jmmi", "dataset")

    st.session_state[SESSION_KEY] = PipelineResponse.model_validate(results)
    # deliberately no switch_page — render the summary right here, below the
    # uploader, so the uploader stays reachable without a trip back

if SESSION_KEY in st.session_state and st.session_state[SESSION_KEY] is not None:
    render_summary(as_pipeline_response(st.session_state[SESSION_KEY]), results_page=RESULTS_PAGE)
else:
    st.info("Upload a file above and run the validation to see the summary here.")
