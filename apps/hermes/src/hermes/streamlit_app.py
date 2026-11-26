import logging

import streamlit as st

logging.getLogger("fastexcel.types.dtype").setLevel(level=logging.ERROR)

st.set_page_config(
    page_title="Hermes - a frontend for Argus Validation",
    layout="wide",
)

page = st.navigation(
    [
        st.Page("pages/about.py", title="About"),
        st.Page("pages/upload.py", title="Upload a file", default=True),
        st.Page("pages/results.py", title="Results Details"),
    ]
)


page.run()
