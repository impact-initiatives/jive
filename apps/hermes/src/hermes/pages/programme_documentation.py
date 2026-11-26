import streamlit as st

from hermes.config import get_settings

settings = get_settings()

st.title("Programme Documentation")
st.markdown("Resources related to programmes and their dataset requirements.")
st.divider()

for key, value in settings.jive_documentation.items():
    st.subheader(key)
    for ikey, ivalue in value.items():
        st.markdown(f"[{ikey}]({ivalue})")
