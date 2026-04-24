import streamlit as st
import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from app.neo4j_client import client

def render_file_view():
    with st.sidebar:
        st.divider()
        search = st.text_input("Search files...")

    modules = client.get_modules()
    if not modules:
        st.info("No files found in Neo4j.")
        return

    gt_files = []
    try:
        state_file = os.path.join(os.path.dirname(__file__), '..', '..', 'cache', 'current_instance.json')
        if os.path.exists(state_file):
            with open(state_file, 'r', encoding='utf-8') as f:
                gt_files = json.load(f).get("gt_files", [])
    except Exception:
        pass

    filtered = [m for m in modules if not search or search.lower() in m.lower()]
    st.caption(f"{len(filtered)} / {len(modules)} files — 🎯 = Ground Truth")

    lines = "\n".join(
        f"🎯  {m}" if m in gt_files else f"    {m}"
        for m in filtered
    )

    st.components.v1.html(
        f"""
        <style>
        * {{ margin: 0; padding: 0; }}
        body {{ background: #1e1e1e; overflow: hidden; }}
        #box {{
            font-family: monospace; font-size: 13px; color: #ddd;
            padding: 8px 12px; white-space: pre; overflow-y: auto;
            height: 90vh;
        }}
        </style>
        <div id="box">{lines}</div>
        """,
        height=900,
        scrolling=False,
    )
