# =============================================================================
# app/components/graph_view.py — Graph View Tab
#
# Render đồ thị tương tác bằng NeoVis.js (wrapper của vis-network).
# NeoVis kết nối TRỰC TIẾP từ browser đến Neo4j Bolt — Streamlit không
# làm trung gian cho data, chỉ serve HTML.
#
# Panel điều khiển bên trái (overlay HTML/CSS):
#   - Depth: BFS depth khi click node (1-4)
#   - Dim mode: làm mờ node/edge không trong highlight set
#   - Community mode: tô màu theo community Leiden
#   - Node type filters: ẩn/hiện Module/Class/Function
#   - Edge type filters: ẩn/hiện Defines/Calls/Imports/Inherits
#
# Tất cả filter/highlight logic chạy trên JavaScript client-side
# (không round-trip về Streamlit) → mượt, không lag.
# =============================================================================

import json
import colorsys
import streamlit as st
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from app.neo4j_client import client
import config

# ── Style constants ───────────────────────────────────────────────────────────
# Màu và kích thước cho từng loại node — khớp với legend trong panel
NODE_STYLES = {
    "Module":   {"color": "#3388ff", "size": 28},   # to nhất — file level
    "Class":    {"color": "#ff7700", "size": 18},   # trung bình
    "Function": {"color": "#22cc66", "size": 10},   # nhỏ nhất — leaf nodes
}

# Màu và style cho từng loại edge
EDGE_STYLES = {
    "Defines":  {"color": "#778899", "width": 1, "dashes": "false"},  # mờ — cấu trúc
    "Calls":    {"color": "#ff4c4c", "width": 2, "dashes": "false"},  # đỏ — gọi hàm
    "Imports":  {"color": "#ffd700", "width": 2, "dashes": "true"},   # vàng nét đứt
    "Inherits": {"color": "#bf5fff", "width": 2, "dashes": "false"},  # tím — kế thừa
}


def _community_palette(n: int) -> list[str]:
    """
    Tạo n màu phân biệt dùng golden ratio hue spacing trên vòng màu HSV.

    Golden ratio (≈0.618) đảm bảo các màu liền kề không giống nhau
    và toàn bộ palette phân bố đều trên spectrum màu.
    """
    golden = 0.618033988749895
    colors = []
    for i in range(n):
        h = (i * golden) % 1.0       # hue trải đều qua golden ratio
        r, g, b = colorsys.hsv_to_rgb(h, 0.88, 0.95)  # saturation cao, value sáng
        colors.append("#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255)))
    return colors


def _build_labels_js() -> str:
    """
    Build JavaScript object config cho NeoVis labels (node styles).

    Format: { Module: { label: "name", [NeoVis.NEOVIS_ADVANCED_CONFIG]: { static: {...} } }, ... }
    NEOVIS_ADVANCED_CONFIG cho phép dùng static config thay vì Neo4j property.
    """
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
    """
    Build JavaScript object config cho NeoVis relationships (edge styles).

    Format: { Calls: { [NeoVis.NEOVIS_ADVANCED_CONFIG]: { static: {...} } }, ... }
    """
    parts = []
    for rel, style in EDGE_STYLES.items():
        parts.append(
            f'{rel}: {{'
            f'[NeoVis.NEOVIS_ADVANCED_CONFIG]: {{'
            f'static: {{ label: "{rel}", color: "{style["color"]}", '
            f'width: {style["width"]}, dashes: {style["dashes"]} }}'
            f'}}}}'
        )
    return "{" + ", ".join(parts) + "}"


def _render_neovis(cypher: str) -> None:
    """
    Tạo và render NeoVis graph trong iframe Streamlit.

    Toàn bộ HTML/CSS/JS được generate server-side (Python) rồi inject vào
    st.components.v1.html(). Data như COMMUNITY_MAP, PALETTE được serialize
    thành JSON và nhúng trực tiếp vào script để tránh API call từ browser.

    Kiến trúc JS:
      - viz.registerOnEvent('completed'): populate lookup tables sau khi NeoVis render
      - applyState(): hàm trung tâm, tính toán visibility/color cho mọi node+edge
      - getNeighborsAtDepth(): BFS client-side dùng vis-network API
      - rebuildBaseColors(): tái tính base colors khi toggle community mode
    """
    # Serialize Python data sang JSON để embed vào JS
    community_map_js     = json.dumps(client.get_community_map())
    palette_js           = json.dumps(_community_palette(50))   # 50 màu đủ cho hầu hết repo
    node_label_colors_js = json.dumps({k: v["color"] for k, v in NODE_STYLES.items()})
    node_styles_js       = json.dumps({k: {"color": v["color"], "size": v["size"]} for k, v in NODE_STYLES.items()})
    edge_styles_js       = json.dumps({k: {"color": v["color"], "width": v["width"]} for k, v in EDGE_STYLES.items()})

    labels_js  = _build_labels_js()
    rels_js    = _build_rels_js()
    # Escape backtick vì Cypher string được đặt trong JS template literal
    cypher_esc = cypher.replace("`", "\\`")

    html = f"""<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/neovis.js@2.0.2"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #1e1e1e; font-family: -apple-system, sans-serif; overflow: hidden; }}
    #viz {{ width: 100vw; height: 100vh; }}

    /* Overlay panel bên trái */
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

    /* Segmented depth control */
    .seg {{ display: flex; border: 1px solid #333; border-radius: 6px; overflow: hidden; }}
    .seg-btn {{
      flex: 1; background: transparent; color: #666; border: none;
      padding: 5px 0; cursor: pointer; font-size: 13px;
      transition: background .1s, color .1s;
    }}
    .seg-btn:not(:last-child) {{ border-right: 1px solid #333; }}
    .seg-btn:hover {{ background: #252525; color: #ccc; }}
    .seg-btn.active {{ background: #1a4a8a; color: #6aacff; font-weight: 700; }}

    /* Checkbox toggle rows */
    .tog {{
      display: flex; align-items: center; gap: 8px;
      cursor: pointer; padding: 1px 0;
    }}
    .tog input[type=checkbox] {{
      accent-color: #3388ff; width: 13px; height: 13px;
      cursor: pointer; flex-shrink: 0; margin: 0;
    }}
    .tog span {{ color: #aaa; font-size: 12px; line-height: 1.4; }}

    /* Legend items với colored dot/line */
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
    .edge-line {{ width: 18px; height: 3px; border-radius: 2px; flex-shrink: 0; }}
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
    <!-- Depth segmented control -->
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

    <!-- Node type filters -->
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

    <!-- Edge type filters -->
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
    /* ── Data từ Python (serialize JSON → JS const) ─────────────────────── */
    const COMMUNITY_MAP     = {community_map_js};   // neo4j_id → community_int
    const PALETTE           = {palette_js};          // list màu hex
    const NODE_LABEL_COLORS = {node_label_colors_js}; // label → hex
    const NODE_STYLES_MAP   = {node_styles_js};       // label → {{color, size}}
    const EDGE_STYLES_MAP   = {edge_styles_js};       // type → {{color, width}}

    /* ── State toàn cục ─────────────────────────────────────────────────── */
    let currentDepth    = 1;
    let lastSelectedId  = null;     // neo4j ID của node đang được chọn
    let highlightedSet  = new Set(); // set ID các node trong BFS highlight

    let _network, _nodesDs, _edgesDs;  // vis-network references (set sau khi NeoVis ready)

    // Lookup tables: populate trong event 'completed' của NeoVis
    const nodeGroupMap  = {{}};  // neo4j_id → "Module"|"Class"|"Function"
    const edgeTypeMap   = {{}};  // neo4j_id → "Calls"|...

    // Base colors — thay đổi khi toggle community mode
    const nodeBaseColor = {{}};  // neo4j_id → hex (hiện tại, có thể là community color)
    const edgeBaseColor = {{}};
    const edgeBaseWidth = {{}};

    // Original colors từ NeoVis config (không đổi)
    const nodeOrigColor = {{}};
    const edgeOrigColor = {{}};
    const edgeOrigWidth = {{}};

    // Visibility sets — quản lý bởi filter checkboxes
    const visibleNodeTypes = new Set(['Module', 'Class', 'Function']);
    const visibleEdgeTypes = new Set(['Defines', 'Calls', 'Imports', 'Inherits']);

    /* ── Color helpers ──────────────────────────────────────────────────── */
    const DIM = 'rgba(200,200,200,0.12)';  // màu mờ cho node không highlight

    // vis-network yêu cầu color object với background, border, highlight, hover
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

    /* ── Depth control ──────────────────────────────────────────────────── */
    function setDepth(val) {{
      currentDepth = val;
      // Cập nhật visual state của segmented control
      document.querySelectorAll('#depthSeg .seg-btn').forEach((b, i) => {{
        b.classList.toggle('active', i + 1 === val);
      }});
      // Tái tính highlight nếu đang có node được chọn
      if (lastSelectedId !== null) applyHighlight();
    }}

    /* ── Filter controls ────────────────────────────────────────────────── */
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

    /* ── NeoVis initialization ──────────────────────────────────────────── */
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
      labels:        {labels_js},
      relationships: {rels_js},
      initialCypher: `{cypher_esc}`
    }});

    /* Event 'completed': NeoVis đã render xong → populate lookup tables */
    viz.registerOnEvent('completed', function() {{
      _network = viz.network;
      _nodesDs = viz.nodes;
      _edgesDs = viz.edges;

      // Populate node lookup tables
      _nodesDs.get().forEach(n => {{
        const grp = (n.raw && n.raw.labels && n.raw.labels[0]) || 'Module';
        nodeGroupMap[n.id] = grp;

        // Lấy màu gốc từ NeoVis config (có thể là object hoặc string)
        const rawColor = n.color;
        const col = (rawColor && typeof rawColor === 'object' ? rawColor.background : null)
                    || (typeof rawColor === 'string' ? rawColor : null)
                    || NODE_LABEL_COLORS[grp]
                    || '#888888';
        nodeOrigColor[n.id] = col;
        nodeBaseColor[n.id] = col;
      }});

      // Populate edge lookup tables
      _edgesDs.get().forEach(e => {{
        const typ = (e.raw && e.raw.type) || e.label || 'Defines';
        edgeTypeMap[e.id]   = typ;
        const st = EDGE_STYLES_MAP[typ] || {{}};
        edgeOrigColor[e.id] = st.color || '#778899';
        edgeOrigWidth[e.id] = st.width || 1;
        edgeBaseColor[e.id] = edgeOrigColor[e.id];
        edgeBaseWidth[e.id] = edgeOrigWidth[e.id];
      }});

      // Click handler: highlight BFS neighbors khi click node
      _network.on('click', function(params) {{
        if (params.nodes.length > 0) {{
          lastSelectedId = params.nodes[0];
          highlightedSet = getNeighborsAtDepth(lastSelectedId, currentDepth);
          applyState();
          _network.unselectAll();  // bỏ selection mặc định của vis-network
        }} else if (lastSelectedId !== null) {{
          // Click vào empty space → clear highlight
          lastSelectedId = null;
          highlightedSet = new Set();
          applyState();
        }}
      }});
    }});

    viz.render();

    /* ── BFS client-side ────────────────────────────────────────────────── */
    // Dùng vis-network API (getConnectedNodes) thay vì query Neo4j lại
    // để tránh network roundtrip khi user click nhiều lần nhanh
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

    /* ── Community color rebuild ────────────────────────────────────────── */
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
          // Edge trong cùng community → màu community; cross-community → xám
          const sc = COMMUNITY_MAP[e.from], ec = COMMUNITY_MAP[e.to];
          edgeBaseColor[e.id] = (sc !== undefined && sc === ec)
            ? PALETTE[sc % PALETTE.length] : '#444444';
        }} else {{
          edgeBaseColor[e.id] = edgeOrigColor[e.id];
        }}
      }});

      applyState();
    }}

    /* ── Apply highlight ────────────────────────────────────────────────── */
    function applyHighlight() {{
      highlightedSet = getNeighborsAtDepth(lastSelectedId, currentDepth);
      applyState();
    }}

    /* ── Central state applier ──────────────────────────────────────────── */
    // Hàm duy nhất cập nhật visual state của toàn bộ graph.
    // Gộp tất cả logic: filter + highlight + dim + community color
    function applyState() {{
      if (!_nodesDs) return;
      const dimMode     = document.getElementById('dimMode').checked;
      const hasSelection = lastSelectedId !== null;

      /* Nodes */
      const nodeUpdates = _nodesDs.get().map(node => {{
        const typ = nodeGroupMap[node.id];
        // Ẩn nếu type bị filter
        if (!visibleNodeTypes.has(typ))
          return {{ id: node.id, hidden: true }};

        if (!hasSelection) {{
          // Không có selection → show tất cả với base color
          return {{ id: node.id, hidden: false,
                    color: nodeColorObj(nodeBaseColor[node.id]),
                    borderWidth: 1, shadow: {{ enabled: false }} }};
        }}

        if (highlightedSet.has(node.id)) {{
          // Trong highlight set → border trắng + shadow để nổi bật
          return {{ id: node.id, hidden: false,
                    color: nodeHighlightObj(nodeBaseColor[node.id]),
                    borderWidth: 3,
                    shadow: {{ enabled: true, color: 'rgba(255,255,255,0.35)',
                               size: 14, x: 0, y: 0 }} }};
        }}

        // Không trong highlight → dim hoặc giữ màu gốc tùy dimMode
        return {{ id: node.id, hidden: false,
                  color: dimMode ? nodeDimObj() : nodeColorObj(nodeBaseColor[node.id]),
                  borderWidth: 1, shadow: {{ enabled: false }} }};
      }});
      _nodesDs.update(nodeUpdates);

      /* Edges */
      const edgeUpdates = _edgesDs.get().map(edge => {{
        const typ        = edgeTypeMap[edge.id];
        const fromHidden = !visibleNodeTypes.has(nodeGroupMap[edge.from]);
        const toHidden   = !visibleNodeTypes.has(nodeGroupMap[edge.to]);

        // Ẩn nếu edge type bị filter hoặc một trong hai endpoint bị ẩn
        if (!visibleEdgeTypes.has(typ) || fromHidden || toHidden)
          return {{ id: edge.id, hidden: true }};

        const baseW = edgeBaseWidth[edge.id] || 1;

        if (!hasSelection) {{
          return {{ id: edge.id, hidden: false,
                    color: edgeColorObj(edgeBaseColor[edge.id]),
                    width: baseW, shadow: {{ enabled: false }} }};
        }}

        if (highlightedSet.has(edge.from) && highlightedSet.has(edge.to)) {{
          // Edge trong highlight → dày gấp đôi + shadow
          return {{ id: edge.id, hidden: false,
                    color: edgeColorObj(edgeBaseColor[edge.id]),
                    width: baseW * 2,
                    shadow: {{ enabled: true, color: 'rgba(255,255,255,0.2)',
                               size: 8, x: 0, y: 0 }} }};
        }}

        return {{ id: edge.id, hidden: false,
                  color: dimMode ? edgeDimObj() : edgeColorObj(edgeBaseColor[edge.id]),
                  width: baseW, shadow: {{ enabled: false }} }};
      }});
      _edgesDs.update(edgeUpdates);
    }}
  </script>
</body>
</html>"""
    # height=900 đủ để hiện graph không bị crop trên màn hình 1080p
    st.components.v1.html(html, height=900, scrolling=False)


def render_graph_view():
    """
    Entry point cho Graph View tab.

    Kiểm tra có data trong Neo4j không, rồi render NeoVis với Cypher
    lấy tất cả node/edge (giới hạn 2000 để tránh browser lag).
    """
    modules = client.get_modules()
    if not modules:
        st.warning("Không có dữ liệu trong Neo4j.")
        return

    # LIMIT 2000: với repo lớn (vd: Django), full graph có thể hàng chục nghìn node
    # NeoVis/vis-network bắt đầu lag rõ khi >2000 node do physics simulation
    cypher = "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 2000"
    _render_neovis(cypher)
