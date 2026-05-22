import sys
import os

import streamlit as st

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.neo4j_client import client
from app.components.file_view import render_file_view
from app.components.combined_view import render_combined_view

st.set_page_config(page_title="GraphRAG POC", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 0.5rem !important; padding-bottom: 0 !important; }
header { visibility: hidden; }
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
title_col, status_col = st.columns([6, 1])
with title_col:
    st.title("GraphRAG POC")
with status_col:
    if client.connected:
        st.success("Neo4j ● connected")
    else:
        st.error("Neo4j ✕ disconnected")
        st.info("Khởi động Neo4j và chạy build_graph.py trước.")
        st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_main, tab_file = st.tabs(["Graph & Query", "File View"])

with tab_main:
    render_combined_view()

with tab_file:
    render_file_view()
