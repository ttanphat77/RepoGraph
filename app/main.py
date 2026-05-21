# =============================================================================
# app/main.py — Streamlit Application Entry Point
#
# Khởi động: streamlit run app/main.py
# Truy cập:  http://localhost:8501
#
# Cấu trúc UI:
#   Sidebar  — trạng thái kết nối Neo4j
#   Tab 1    — Graph + Query : NeoVis graph (cột phải) + RAG query (cột trái)
#   Tab 2    — File View     : danh sách file với highlight GT files
# =============================================================================

import sys
import os

import streamlit as st

# Thêm project root để import pipeline và config
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.neo4j_client import client
from app.components.file_view import render_file_view
from app.components.combined_view import render_combined_view

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="GraphRAG POC", layout="wide")

# Ẩn header mặc định của Streamlit và giảm padding để tận dụng không gian màn hình
st.markdown("""
<style>
.block-container { padding-top: 0.5rem !important; padding-bottom: 0 !important; }
header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("GraphRAG POC")

# ── Sidebar: trạng thái kết nối ──────────────────────────────────────────────
with st.sidebar:
    if client.connected:
        st.success("Neo4j: ● connected")
    else:
        st.error("Neo4j: ✕ disconnected")
        st.info("Khởi động Neo4j và chạy build_graph.py trước.")
        st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_main, tab_file = st.tabs(["Graph & Query", "File View"])

with tab_main:
    # Cột trái: RAG query controls + results
    # Cột phải: NeoVis graph với highlight từ kết quả query
    render_combined_view()

with tab_file:
    # Danh sách file với tìm kiếm và highlight GT files (🎯)
    render_file_view()
