import json
import colorsys
import streamlit as st
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from app.neo4j_client import client
import config

NODE_STYLES = {
    "Module":   {"color": "#3388ff", "size": 28},
    "Class":    {"color": "#ff7700", "size": 18},
    "Function": {"color": "#22cc66", "size": 10},
}

EDGE_STYLES = {
    "Defines":  {"color": "#778899", "width": 1, "dashes": "false"},
    "Calls":    {"color": "#ff4c4c", "width": 2, "dashes": "false"},
    "Imports":  {"color": "#ffd700", "width": 2, "dashes": "true"},
    "Inherits": {"color": "#bf5fff", "width": 2, "dashes": "false"},
}


def _community_palette(n: int) -> list[str]:
    golden = 0.618033988749895
    colors = []
    for i in range(n):
        h = (i * golden) % 1.0
        r, g, b = colorsys.hsv_to_rgb(h, 0.88, 0.95)
        colors.append("#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255)))
    return colors


def _build_labels_js() -> str:
    parts = []
    for label, style in NODE_STYLES.items():
        parts.append(
            f'{label}: {{'
            f'label: "name", '
            f'[NeoVis.NEOVIS_ADVANCED_CONFIG]: {{'
            f'static: {{ shape: "dot", size: {style["size"]}, color: "{style["color"]}" }}'
            f'}}}}'
        )
    return "{" + ", ".join(parts) + "}"


def _build_rels_js() -> str:
    parts = []
    for rel, style in EDGE_STYLES.items():
        parts.append(
            f'{rel}: {{'
            f'[NeoVis.NEOVIS_ADVANCED_CONFIG]: {{'
            f'static: {{ label: "{rel}", color: "{style["color"]}", width: {style["width"]}, dashes: {style["dashes"]} }}'
            f'}}}}'
        )
    return "{" + ", ".join(parts) + "}"


def _render_neovis(cypher: str) -> None:
    community_map_js     = json.dumps(client.get_community_map())
    palette_js           = json.dumps(_community_palette(50))
    node_label_colors_js = json.dumps({k: v["color"] for k, v in NODE_STYLES.items()})
    node_styles_js       = json.dumps({k: {"color": v["color"], "size": v["size"]} for k, v in NODE_STYLES.items()})
    edge_styles_js       = json.dumps({k: {"color": v["color"], "width": v["width"]} for k, v in EDGE_STYLES.items()})

    labels_js  = _build_labels_js()
    rels_js    = _build_rels_js()
    cypher_esc = cypher.replace("`", "\\`")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/neovis.js@2.0.2"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #1e1e1e; font-family: -apple-system, sans-serif; overflow: hidden; }}
    #viz {{ width: 100vw; height: 100vh; }}

    #panel {{
      position: absolute; top: 12px; left: 12px; z-index: 100;
      background: rgba(18,18,18,0.95); border: 1px solid #2e2e2e;
      border-radius: 10px; padding: 14px;
      display: flex; flex-direction: column; gap: 10px;
      width: 220px;
      box-shadow: 0 6px 24px rgba(0,0,0,0.7);
      user-select: none;
    }}

    .section-title {{
      color: #555; font-size: 10px; text-transform: uppercase;
      letter-spacing: .1em; font-weight: 600;
    }}

    /* segmented depth control */
    .seg {{ display: flex; border: 1px solid #333; border-radius: 6px; overflow: hidden; }}
    .seg-btn {{
      flex: 1; background: transparent; color: #666; border: none;
      padding: 5px 0; cursor: pointer; font-size: 13px;
      transition: background .1s, color .1s;
    }}
    .seg-btn:not(:last-child) {{ border-right: 1px solid #333; }}
    .seg-btn:hover {{ background: #252525; color: #ccc; }}
    .seg-btn.active {{ background: #1a4a8a; color: #6aacff; font-weight: 700; }}

    /* checkbox rows */
    .tog {{
      display: flex; align-items: center; gap: 8px;
      cursor: pointer; padding: 1px 0;
    }}
    .tog input[type=checkbox] {{
      accent-color: #3388ff; width: 13px; height: 13px;
      cursor: pointer; flex-shrink: 0; margin: 0;
    }}
    .tog span {{ color: #aaa; font-size: 12px; line-height: 1.4; }}

    /* legend dots & lines */
    .legend-item {{
      display: flex; align-items: center; gap: 8px;
      cursor: pointer; padding: 1px 0;
    }}
    .legend-item input[type=checkbox] {{
      accent-color: #3388ff; width: 13px; height: 13px;
      cursor: pointer; flex-shrink: 0; margin: 0;
    }}
    .legend-item span {{ color: #aaa; font-size: 12px; }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
    .edge-line {{
      width: 18px; height: 3px; border-radius: 2px; flex-shrink: 0;
    }}
    .edge-dashed {{
      width: 18px; height: 0; flex-shrink: 0;
      border-top: 3px dashed;
    }}

    hr.divider {{ border: none; border-top: 1px solid #2a2a2a; margin: 0; }}
  </style>
</head>
<body>
  <div id="viz"></div>

  <div id="panel">
    <!-- Depth -->
    <div style="display:flex;align-items:center;gap:10px;">
      <span class="section-title">Depth</span>
      <div class="seg" id="depthSeg">
        <button class="seg-btn active" onclick="setDepth(1)">1</button>
        <button class="seg-btn"        onclick="setDepth(2)">2</button>
        <button class="seg-btn"        onclick="setDepth(3)">3</button>
        <button class="seg-btn"        onclick="setDepth(4)">4</button>
      </div>
    </div>

    <label class="tog">
      <input type="checkbox" id="dimMode">
      <span>Ẩn node/edge không highlight</span>
    </label>
    <label class="tog">
      <input type="checkbox" id="communityMode">
      <span>Hiện Communities</span>
    </label>

    <hr class="divider">

    <!-- Node filters -->
    <span class="section-title">Nodes</span>
    <label class="legend-item">
      <input type="checkbox" id="f-Module" checked onchange="toggleNodeType('Module',this.checked)">
      <span class="dot" style="background:#3388ff"></span>
      <span>Module</span>
    </label>
    <label class="legend-item">
      <input type="checkbox" id="f-Class" checked onchange="toggleNodeType('Class',this.checked)">
      <span class="dot" style="background:#ff7700"></span>
      <span>Class</span>
    </label>
    <label class="legend-item">
      <input type="checkbox" id="f-Function" checked onchange="toggleNodeType('Function',this.checked)">
      <span class="dot" style="background:#22cc66"></span>
      <span>Function</span>
    </label>

    <hr class="divider">

    <!-- Edge filters -->
    <span class="section-title">Edges</span>
    <label class="legend-item">
      <input type="checkbox" id="f-Defines" checked onchange="toggleEdgeType('Defines',this.checked)">
      <span class="edge-line" style="background:#778899"></span>
      <span>Defines</span>
    </label>
    <label class="legend-item">
      <input type="checkbox" id="f-Calls" checked onchange="toggleEdgeType('Calls',this.checked)">
      <span class="edge-line" style="background:#ff4c4c"></span>
      <span>Calls</span>
    </label>
    <label class="legend-item">
      <input type="checkbox" id="f-Imports" checked onchange="toggleEdgeType('Imports',this.checked)">
      <span class="edge-dashed" style="border-color:#ffd700"></span>
      <span>Imports</span>
    </label>
    <label class="legend-item">
      <input type="checkbox" id="f-Inherits" checked onchange="toggleEdgeType('Inherits',this.checked)">
      <span class="edge-line" style="background:#bf5fff"></span>
      <span>Inherits</span>
    </label>
  </div>

  <script>
    /* ── data from Python ───────────────────────────────────────── */
    const COMMUNITY_MAP     = {community_map_js};
    const PALETTE           = {palette_js};
    const NODE_LABEL_COLORS = {node_label_colors_js};
    const NODE_STYLES_MAP   = {node_styles_js};
    const EDGE_STYLES_MAP   = {edge_styles_js};

    /* ── state ──────────────────────────────────────────────────── */
    let currentDepth    = 1;
    let lastSelectedId  = null;
    let highlightedSet  = new Set();

    let _network, _nodesDs, _edgesDs;

    // per-element lookup tables (populated in 'completed')
    const nodeGroupMap  = {{}};   // id → "Module"|"Class"|"Function"
    const edgeTypeMap   = {{}};   // id → "Calls"|...

    // base colors — rebuilt whenever community mode changes
    const nodeBaseColor = {{}};   // id → hex string
    const edgeBaseColor = {{}};   // id → hex string
    const edgeBaseWidth = {{}};   // id → number

    // original colors/widths from NeoVis static config (never changes)
    const nodeOrigColor = {{}};
    const edgeOrigColor = {{}};
    const edgeOrigWidth = {{}};

    // visibility sets
    const visibleNodeTypes = new Set(['Module', 'Class', 'Function']);
    const visibleEdgeTypes = new Set(['Defines', 'Calls', 'Imports', 'Inherits']);

    /* ── color helpers ──────────────────────────────────────────── */
    const DIM = 'rgba(200,200,200,0.12)';

    function nodeColorObj(hex) {{
      return {{ background: hex, border: hex,
                highlight: {{ background: hex, border: hex }},
                hover:      {{ background: hex, border: hex }} }};
    }}

    function nodeHighlightObj(hex) {{
      return {{ background: hex, border: '#ffffff',
                highlight: {{ background: hex, border: '#ffe066' }},
                hover:      {{ background: hex, border: '#ffffff' }} }};
    }}

    function nodeDimObj() {{
      return {{ background: DIM, border: DIM,
                highlight: {{ background: DIM, border: DIM }},
                hover:      {{ background: DIM, border: DIM }} }};
    }}

    function edgeColorObj(hex) {{
      return {{ color: hex, highlight: hex, hover: hex, inherit: false, opacity: 1 }};
    }}

    function edgeDimObj() {{
      return {{ color: DIM, highlight: DIM, hover: DIM, inherit: false, opacity: 1 }};
    }}

    /* ── depth control ──────────────────────────────────────────── */
    function setDepth(val) {{
      currentDepth = val;
      document.querySelectorAll('#depthSeg .seg-btn').forEach((b, i) => {{
        b.classList.toggle('active', i + 1 === val);
      }});
      if (lastSelectedId !== null) applyHighlight();
    }}

    /* ── filter controls ────────────────────────────────────────── */
    function toggleNodeType(type, checked) {{
      checked ? visibleNodeTypes.add(type) : visibleNodeTypes.delete(type);
      applyState();
    }}

    function toggleEdgeType(type, checked) {{
      checked ? visibleEdgeTypes.add(type) : visibleEdgeTypes.delete(type);
      applyState();
    }}

    document.getElementById('dimMode').addEventListener('change', applyState);
    document.getElementById('communityMode').addEventListener('change', rebuildBaseColors);

    /* ── NeoVis init ────────────────────────────────────────────── */
    const viz = new NeoVis.default({{
      containerId: "viz",
      neo4j: {{
        serverUrl:      "{config.NEO4J_URI}",
        serverUser:     "{config.NEO4J_USER}",
        serverPassword: "{config.NEO4J_PASSWORD}"
      }},
      visConfig: {{
        nodes: {{ font: {{ color: "#ffffff", size: 12, strokeWidth: 0 }}, chosen: false }},
        edges: {{
          font: {{ color: "#cccccc", size: 9, strokeWidth: 0 }},
          arrows: {{ to: {{ enabled: true, scaleFactor: 0.5 }} }},
          chosen: false
        }},
        physics: {{ stabilization: {{ iterations: 200 }} }}
      }},
      labels: {labels_js},
      relationships: {rels_js},
      initialCypher: `{cypher_esc}`
    }});

    viz.registerOnEvent('completed', function() {{
      _network = viz.network;
      _nodesDs = viz.nodes;
      _edgesDs = viz.edges;

      _nodesDs.get().forEach(n => {{
        const grp = (n.raw && n.raw.labels && n.raw.labels[0]) || 'Module';
        nodeGroupMap[n.id] = grp;

        const rawColor = n.color;
        const col = (rawColor && typeof rawColor === 'object' ? rawColor.background : null)
                    || (typeof rawColor === 'string' ? rawColor : null)
                    || NODE_LABEL_COLORS[grp]
                    || '#888888';
        nodeOrigColor[n.id] = col;
        nodeBaseColor[n.id] = col;
      }});

      _edgesDs.get().forEach(e => {{
        const typ = (e.raw && e.raw.type) || e.label || 'Defines';
        edgeTypeMap[e.id]   = typ;
        const st = EDGE_STYLES_MAP[typ] || {{}};
        edgeOrigColor[e.id] = st.color || '#778899';
        edgeOrigWidth[e.id] = st.width || 1;
        edgeBaseColor[e.id] = edgeOrigColor[e.id];
        edgeBaseWidth[e.id] = edgeOrigWidth[e.id];
      }});

      _network.on('click', function(params) {{
        if (params.nodes.length > 0) {{
          lastSelectedId = params.nodes[0];
          highlightedSet = getNeighborsAtDepth(lastSelectedId, currentDepth);
          applyState();
          _network.unselectAll();
        }} else if (lastSelectedId !== null) {{
          lastSelectedId = null;
          highlightedSet = new Set();
          applyState();
        }}
      }});
    }});

    viz.render();

    /* ── BFS ────────────────────────────────────────────────────── */
    function getNeighborsAtDepth(startId, depth) {{
      const visited = new Set([startId]);
      let frontier = [startId];
      for (let d = 0; d < depth; d++) {{
        const next = [];
        for (const nId of frontier)
          for (const nb of _network.getConnectedNodes(nId))
            if (!visited.has(nb)) {{ visited.add(nb); next.push(nb); }}
        frontier = next;
      }}
      return visited;
    }}

    /* ── community rebuild ──────────────────────────────────────── */
    function rebuildBaseColors() {{
      if (!_nodesDs) return;
      const useCommunity = document.getElementById('communityMode').checked;

      _nodesDs.get().forEach(n => {{
        nodeBaseColor[n.id] = useCommunity
          ? PALETTE[(COMMUNITY_MAP[n.id] || 0) % PALETTE.length]
          : nodeOrigColor[n.id];
      }});

      _edgesDs.get().forEach(e => {{
        if (useCommunity) {{
          const sc = COMMUNITY_MAP[e.from], ec = COMMUNITY_MAP[e.to];
          edgeBaseColor[e.id] = (sc !== undefined && sc === ec)
            ? PALETTE[sc % PALETTE.length] : '#444444';
        }} else {{
          edgeBaseColor[e.id] = edgeOrigColor[e.id];
        }}
      }});

      applyState();
    }}

    /* ── apply highlight then recompute selection ───────────────── */
    function applyHighlight() {{
      highlightedSet = getNeighborsAtDepth(lastSelectedId, currentDepth);
      applyState();
    }}

    /* ── central state applier ──────────────────────────────────── */
    function applyState() {{
      if (!_nodesDs) return;
      const dimMode  = document.getElementById('dimMode').checked;
      const hasSelection = lastSelectedId !== null;

      /* nodes */
      const nodeUpdates = _nodesDs.get().map(node => {{
        const typ = nodeGroupMap[node.id];
        // hidden by type filter
        if (!visibleNodeTypes.has(typ))
          return {{ id: node.id, hidden: true }};

        if (!hasSelection) {{
          return {{ id: node.id, hidden: false,
                    color: nodeColorObj(nodeBaseColor[node.id]),
                    borderWidth: 1,
                    shadow: {{ enabled: false }} }};
        }}

        if (highlightedSet.has(node.id)) {{
          return {{ id: node.id, hidden: false,
                    color: nodeHighlightObj(nodeBaseColor[node.id]),
                    borderWidth: 3,
                    shadow: {{ enabled: true, color: 'rgba(255,255,255,0.35)',
                               size: 14, x: 0, y: 0 }} }};
        }}

        return {{ id: node.id, hidden: false,
                  color: dimMode ? nodeDimObj() : nodeColorObj(nodeBaseColor[node.id]),
                  borderWidth: 1,
                  shadow: {{ enabled: false }} }};
      }});
      _nodesDs.update(nodeUpdates);

      /* edges */
      const edgeUpdates = _edgesDs.get().map(edge => {{
        const typ = edgeTypeMap[edge.id];
        const fromHidden = !visibleNodeTypes.has(nodeGroupMap[edge.from]);
        const toHidden   = !visibleNodeTypes.has(nodeGroupMap[edge.to]);

        // hidden by type filter or endpoint node hidden
        if (!visibleEdgeTypes.has(typ) || fromHidden || toHidden)
          return {{ id: edge.id, hidden: true }};

        const baseW = edgeBaseWidth[edge.id] || 1;

        if (!hasSelection) {{
          return {{ id: edge.id, hidden: false,
                    color: edgeColorObj(edgeBaseColor[edge.id]),
                    width: baseW,
                    shadow: {{ enabled: false }} }};
        }}

        if (highlightedSet.has(edge.from) && highlightedSet.has(edge.to)) {{
          return {{ id: edge.id, hidden: false,
                    color: edgeColorObj(edgeBaseColor[edge.id]),
                    width: baseW * 2,
                    shadow: {{ enabled: true, color: 'rgba(255,255,255,0.2)',
                               size: 8, x: 0, y: 0 }} }};
        }}

        return {{ id: edge.id, hidden: false,
                  color: dimMode ? edgeDimObj() : edgeColorObj(edgeBaseColor[edge.id]),
                  width: baseW,
                  shadow: {{ enabled: false }} }};
      }});
      _edgesDs.update(edgeUpdates);
    }}
  </script>
</body>
</html>"""
    st.components.v1.html(html, height=900, scrolling=False)


def render_graph_view():
    modules = client.get_modules()
    if not modules:
        st.warning("Không có dữ liệu trong Neo4j.")
        return
    cypher = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 2000"
    _render_neovis(cypher)
