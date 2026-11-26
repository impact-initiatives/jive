import logging

import streamlit as st

from hermes.config import get_settings

settings = get_settings()

logging.getLogger("fastexcel.types.dtype").setLevel(level=logging.ERROR)

st.set_page_config(
    page_title="Hermes - A Frontend for Argus Data Validation",
    layout="wide",
)

page = st.navigation(
    {
        "Validator": [
            st.Page("pages/upload.py", title="Upload a file", default=True),
            st.Page("pages/results.py", title="Results Details"),
        ],
        "Resources": [
            st.Page("pages/about.py", title="About"),
            st.Page("pages/programme_documentation.py", title="Programme Documentation"),
        ],
    }
)

st.sidebar.markdown(f"Version: {settings.jive_version}")


page.run()
