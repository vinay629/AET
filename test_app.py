import streamlit as st

st.title("Test Dashboard")
st.write("If you see this, Streamlit is working!")

if st.button("Test Button"):
    st.success("Button clicked!")
