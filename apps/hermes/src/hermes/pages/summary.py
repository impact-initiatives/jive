import streamlit as st

from hermes.common import RESULTS_PAGE, SESSION_KEY, as_pipeline_response, render_summary

st.title("Results Summary")

if SESSION_KEY not in st.session_state or st.session_state[SESSION_KEY] is None:
    st.info("No validation results yet. Validate a dataset on the main page first.")
    st.stop()

render_summary(as_pipeline_response(st.session_state[SESSION_KEY]), results_page=RESULTS_PAGE)
