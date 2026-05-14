"""Test Streamlit app."""

import streamlit as st
import sys

print("TEST APP: Starting to load...", file=sys.stderr)

st.set_page_config(page_title="Test", layout="wide")

st.title("Test Dashboard")
st.write("If you can see this, Streamlit is working!")

if st.button("Test Button"):
    st.success("Button clicked!")

print("TEST APP: Finished loading", file=sys.stderr)
