# =============================================================================
# app/components/file_view.py — File View Tab
#
# Hiển thị danh sách tất cả file đã parse trong graph, với:
#   - Tìm kiếm realtime (filter theo tên file)
#   - Highlight 🎯 cho Ground Truth files (từ current_instance.json)
#   - Đếm số file hiện / tổng số
#
# Dùng st.components.v1.html() để render custom HTML với monospace font
# và scroll, thay vì st.write() vì cần scroll riêng không ảnh hưởng page.
# =============================================================================

import streamlit as st
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from app.neo4j_client import client


def render_file_view():
    """Render tab File View — danh sách file với search và GT highlight."""

    search = st.text_input("Search files...")

    # ── Lấy data ──────────────────────────────────────────────────────────────
    modules = client.get_modules()
    if not modules:
        st.info("No files found in Neo4j.")
        return

    # Đọc GT files từ cache state của instance hiện tại
    gt_files = []
    try:
        state_file = os.path.join(
            os.path.dirname(__file__), "..", "..", "cache", "current_instance.json"
        )
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                gt_files = json.load(f).get("gt_files", [])
    except Exception:
        pass  # Nếu không có cache, chạy bình thường không highlight

    # ── Filter theo search ────────────────────────────────────────────────────
    filtered = [m for m in modules if not search or search.lower() in m.lower()]
    st.caption(f"{len(filtered)} / {len(modules)} files — 🎯 = Ground Truth")

    # ── Build display text ────────────────────────────────────────────────────
    # Mỗi dòng: "🎯  path/to/file.py" hoặc "    path/to/file.py"
    # Dùng khoảng trắng thay icon cho file thường để align cột
    lines = "\n".join(
        f"🎯  {m}" if m in gt_files else f"    {m}"
        for m in filtered
    )

    # ── Render HTML scrollable box ────────────────────────────────────────────
    # Dùng custom HTML thay st.text_area vì st.text_area không cho scroll riêng
    # và không render emoji đúng trong monospace font trên một số browser.
    st.components.v1.html(
        f"""
        <style>
        * {{ margin: 0; padding: 0; }}
        body {{ background: #1e1e1e; overflow: hidden; }}
        #box {{
            font-family: monospace;
            font-size: 13px;
            color: #ddd;
            padding: 8px 12px;
            white-space: pre;    /* giữ indent và emoji align */
            overflow-y: auto;
            height: 90vh;
        }}
        </style>
        <div id="box">{lines}</div>
        """,
        height=900,
        scrolling=False,
    )
