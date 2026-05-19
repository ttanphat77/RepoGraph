# =============================================================================
# app/main.py — Streamlit Application Entry Point
#
# Khởi động: streamlit run app/main.py
# Truy cập:  http://localhost:8501
#
# Cấu trúc UI:
#   Sidebar  — trạng thái kết nối Neo4j
#   Tab 1    — Graph View  : đồ thị tương tác NeoVis.js
#   Tab 2    — File View   : danh sách file với highlight GT files
#   Tab 3    — Issue Query : RAG retrieval + LLM generation
# =============================================================================

import sys
import os

import streamlit as st

# Thêm project root để import pipeline và config
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.neo4j_client import client
from app.components.file_view import render_file_view
from app.components.graph_view import render_graph_view
from app.components.query_view import render_query_view

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
        # st.stop() dừng render toàn bộ app — không hiển thị tabs khi không có data
        st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_graph, tab_file, tab_query = st.tabs(["Graph View", "File View", "Issue Query"])

with tab_graph:
    # Đồ thị tương tác NeoVis.js — kết nối trực tiếp từ browser đến Neo4j
    render_graph_view()

with tab_file:
    # Danh sách file với tìm kiếm và highlight GT files (🎯)
    render_file_view()

with tab_query:
    # RAG retrieval: issue text → graph → LLM → predicted files
    render_query_view()
