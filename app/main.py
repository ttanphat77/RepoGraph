import sys
import os
import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.neo4j_client import client
from app.components.file_view import render_file_view
from app.components.graph_view import render_graph_view

st.set_page_config(page_title="GraphRAG POC", layout="wide")
st.markdown("""
<style>
.block-container { padding-top: 0.5rem !important; padding-bottom: 0 !important; }
header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)
st.title("GraphRAG POC")

with st.sidebar:
    if client.connected:
        st.success("Neo4j: ● connected")
    else:
        st.error("Neo4j: ✕ disconnected")
        st.info("Khởi động Neo4j và chạy build_graph.py trước.")
        st.stop()

tab_graph, tab_file = st.tabs(["Graph View", "File View"])

with tab_graph:
    render_graph_view()

with tab_file:
    render_file_view()
