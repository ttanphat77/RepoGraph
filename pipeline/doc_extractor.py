# =============================================================================
# pipeline/doc_extractor.py — Lớp doc của graph đa nguồn
#
# Thiết kế: mục 2.2 pipeline_design.md (đã dùng ở các lượt v3, v4 của notebook).
#
# Module này xử lý:
#   1. Tìm thư mục doc đầu tiên tồn tại (docs, doc, documentation, Documentation)
#      và liệt kê file .rst / .md / .txt, bỏ thư mục build/generated.
#   2. Mỗi file → 1 node Document; chia theo heading RST → nhiều node DocChunk
#      (cạnh HasChunk). Đoạn dài hơn MAX_CHUNK_CHARS được cắt tiếp theo đoạn văn,
#      mỗi phần vẫn giữ heading.
#   3. Bắt tham chiếu tới code trong role Sphinx (:func:, :meth:, :class:, ...) và
#      directive (.. autoclass::, .. method::, ...) → cạnh Documents (DocChunk → Function/Class).
#      Bắt :doc: → cạnh References (DocChunk → Document).
#
# Cách nối tên (bản v2):
#   Bảng tên giữ MỌI node khớp một tên (module.name, pkg.name, tên trơn, Class.name,
#   pkg.Class.name). Tên được thử kèm module ngữ cảnh (.. module:: / .. currentmodule::)
#   trước. Nhiều node khớp → chỉ giữ node trong module ngữ cảnh. Vẫn mơ hồ → không nối.
#
# Format output giống ASTEngine.parse():
#   node = {"labels": [label], "id": ..., "properties": {...}}
#   edge = {"type": ..., "source": ..., "target": ...}
# =============================================================================

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

# Đoạn dài hơn ngưỡng này được cắt tiếp theo đoạn văn (~400 token).
MAX_CHUNK_CHARS = 1600

# Ký tự gạch chân heading RST (===, ---, ~~~, ...)
_RST_ADORN = set("=-~^*+#<>")

_DOC_DIR_CANDIDATES = ("docs", "doc", "documentation", "Documentation")
_DOC_SKIP = {"_build", "_static", "_templates", "_themes", "generated", "auto_examples"}

# Role Sphinx trỏ tới đối tượng Python: :func:`x`, :meth:`x`, ...
_ROLE_RE = re.compile(r":(?:func|meth|class|attr|exc|obj):`([^`]+)`")
# Directive định nghĩa đối tượng: .. autoclass:: x, .. class:: x, .. py:method:: x.
# Tên dừng ở "(" → bỏ chữ ký: ".. class:: Model(**kwargs)" → "Model"
_DIR_RE = re.compile(
    r"\.\.\s+(?:py:)?(?:auto)?(function|class|method|exception|attribute|decorator)::\s+([~\w.]+)"
)
# Tham chiếu doc → doc
_DOC_RE = re.compile(r":doc:`([^`]+)`")
# Module ngữ cảnh: .. module:: x / .. currentmodule:: x
_MOD_RE = re.compile(r"\.\.\s+(?:current)?module::\s+(\S+)")


def get_doc_files(repo_path: str) -> list[str]:
    """
    Liệt kê file doc (.rst/.md/.txt) trong thư mục doc đầu tiên tồn tại.

    Trả về đường dẫn tương đối (dấu /). Repo không có thư mục doc → [].
    File .txt tên requirements*/robots* không phải doc nên bị bỏ.
    """
    repo = Path(repo_path)
    docs_dir = next((repo / d for d in _DOC_DIR_CANDIDATES if (repo / d).is_dir()), None)
    if docs_dir is None:
        return []
    out = []
    for ext in ("*.rst", "*.md", "*.txt"):  # Django viết doc RST trong file .txt
        for p in sorted(docs_dir.rglob(ext)):
            if any(part in _DOC_SKIP for part in p.parts):
                continue
            if p.suffix == ".txt" and p.name.lower().startswith(("requirements", "robots")):
                continue
            out.append(str(p.relative_to(repo)).replace("\\", "/"))
    return out


def _is_underline(line: str) -> bool:
    """Dòng chỉ gồm một ký tự gạch chân RST lặp lại."""
    s = line.strip()
    return bool(s) and s[0] in _RST_ADORN and all(c == s[0] for c in s)


def _headings(lines: list[str]) -> list[tuple[int, str]]:
    """Vị trí (dòng tiêu đề, tiêu đề) của mọi heading RST: tiêu đề có gạch chân dài ít nhất bằng nó."""
    out = []
    for i in range(1, len(lines)):
        if _is_underline(lines[i]):
            prev = lines[i - 1].strip()
            if prev and len(lines[i].strip()) >= len(prev):
                out.append((i - 1, prev))
    return out


def _maybe_split(heading: str, body: str) -> list[tuple[str, str]]:
    """Body dài hơn MAX_CHUNK_CHARS → cắt theo đoạn văn, mỗi phần giữ heading."""
    if len(body) <= MAX_CHUNK_CHARS:
        return [(heading, body)]
    parts, cur, cur_len = [], [], 0
    for para in re.split(r"\n\n+", body):
        plen = len(para)
        if cur and cur_len + plen > MAX_CHUNK_CHARS:
            parts.append((heading, "\n\n".join(cur)))
            cur, cur_len = [para], plen
        else:
            cur.append(para)
            cur_len += plen
    if cur:
        parts.append((heading, "\n\n".join(cur)))
    return parts or [(heading, body)]


def split_chunks(text: str) -> list[tuple[str, str]]:
    """
    Chia nội dung một file doc thành các (heading, body).

    Mỗi heading RST mở một chunk, body chạy tới heading kế tiếp. Chunk rỗng bị bỏ.
    File không có heading nào → cả file là một chunk với heading rỗng.
    """
    lines = text.splitlines()
    bounds = _headings(lines)
    if not bounds:
        body = "\n".join(lines).strip()
        return [("", body)] if body else []
    chunks = []
    for idx, (pos, heading) in enumerate(bounds):
        start = pos + 2
        end = bounds[idx + 1][0] if idx + 1 < len(bounds) else len(lines)
        body = "\n".join(lines[start:end]).strip()
        if body:
            chunks.extend(_maybe_split(heading, body))
    return chunks


class DocExtractor:
    """Một file doc → node Document + các DocChunk + tham chiếu chờ nối với code."""

    def __init__(self, rel_path: str, repo_path: str):
        self.rel_path = rel_path
        self.abs_path = Path(repo_path) / rel_path

    def extract(self) -> dict | None:
        """
        Returns:
            dict gồm doc_id, nodes, edges (HasChunk),
            pending_links [(chunk_id, tên, module ngữ cảnh)] và pending_refs [(chunk_id, đích :doc:)].
            None nếu không đọc được file.
        """
        try:
            text = self.abs_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
        return self.extract_text(text)

    def extract_text(self, text: str) -> dict:
        """Như extract() nhưng nhận sẵn nội dung file (dùng cho test)."""
        doc_id = f"doc:{self.rel_path}"
        bounds = _headings(text.splitlines())
        nodes = [{
            "labels": ["Document"], "id": doc_id,
            "properties": {
                "file":  self.rel_path,
                "type":  Path(self.rel_path).suffix.lstrip("."),
                "title": bounds[0][1] if bounds else Path(self.rel_path).stem,
            },
        }]
        edges, pending_links, pending_refs = [], [], []
        current_module = None  # ngữ cảnh .. module:: hiện hành
        current_class = None   # class gần nhất, cho .. method:: không có tiền tố class

        for i, (heading, body) in enumerate(split_chunks(text)):
            cid = f"chunk:{self.rel_path}:{i}"
            nodes.append({
                "labels": ["DocChunk"], "id": cid,
                "properties": {"file": self.rel_path, "heading": heading, "index": i, "text": body},
            })
            edges.append({"type": "HasChunk", "source": doc_id, "target": cid})

            combined = f"{heading}\n{body}"
            for m in _MOD_RE.finditer(combined):
                v = m.group(1)
                current_module = None if v == "None" else v
                current_class = None
            for m in _DIR_RE.finditer(combined):
                kind, name = m.group(1), m.group(2)
                if kind == "class":
                    current_class = name.lstrip("~.").split(".")[-1]
                elif kind in ("method", "attribute") and "." not in name and current_class:
                    name = f"{current_class}.{name}"
                pending_links.append((cid, name, current_module))
            for m in _ROLE_RE.finditer(combined):
                pending_links.append((cid, m.group(1), current_module))
            for m in _DOC_RE.finditer(combined):
                pending_refs.append((cid, m.group(1)))

        return {"doc_id": doc_id, "nodes": nodes, "edges": edges,
                "pending_links": pending_links, "pending_refs": pending_refs}


def _file_module(file: str) -> str:
    """Đường dẫn file → tên module dạng chấm. Bỏ tiền tố src. và đuôi .__init__ (doc không viết src.)."""
    m = file.replace("/", ".").removesuffix(".py").removesuffix(".__init__")
    return m[4:] if m.startswith("src.") else m


def build_name_index(code_nodes: list[dict]) -> dict[str, set[str]]:
    """
    Bảng tên → mọi id Function/Class có tên đó.

    Mỗi node đăng ký các khóa: module.name, pkg.name (dạng re-export như flask.url_for),
    name, Class.name và pkg.Class.name. File test không được đăng ký, vì doc không
    document test và tên trong test hay trùng tên trong source.
    """
    idx: dict[str, set[str]] = defaultdict(set)
    for n in code_nodes:
        if n["labels"][0] not in ("Function", "Class"):
            continue
        nid = n["id"]
        name = n["properties"].get("name", "")
        file = n["properties"].get("file", "")
        if not name:
            continue
        parts = file.split("/")
        if any(p in ("test", "tests", "testing") for p in parts) or parts[-1].startswith("test_"):
            continue
        file_mod = _file_module(file)
        pkg = file_mod.split(".")[0]
        keys = {f"{file_mod}.{name}", f"{pkg}.{name}", name}
        rest = nid.split(f":{file}:", 1)
        if len(rest) == 2:
            nested = rest[1].split(":")
            if len(nested) >= 2:
                keys |= {f"{nested[-2]}.{name}", f"{pkg}.{nested[-2]}.{name}"}
        for k in keys:
            idx[k].add(nid)
    return idx


def resolve_doc_links(doc_results: list[dict], name_index: dict[str, set[str]]) -> list[dict]:
    """
    Nối tham chiếu chờ → cạnh Documents (doc → code) và References (doc → doc), bỏ trùng.

    Documents: thử lần lượt tên kèm module ngữ cảnh, tên như doc viết, Class.method, tên cuối.
    Khóa đầu tiên có ứng viên quyết định. Một node → nối. Nhiều node → chỉ giữ node nằm
    trong module ngữ cảnh. Vẫn mơ hồ → không nối, không chọn bừa một node trùng tên.
    """
    doc_ids = {r["doc_id"] for r in doc_results}
    edges, seen = [], set()

    for r in doc_results:
        for cid, raw, cur_mod in r["pending_links"]:
            name = raw.strip()
            m = re.search(r"<([^<>]+)>$", name)  # role có tiêu đề riêng: `text <target>`
            if m:
                name = m.group(1)
            name = name.lstrip("~.").removesuffix("()")
            tries = ([f"{cur_mod}.{name}"] if cur_mod else []) + [
                name, ".".join(name.split(".")[-2:]), name.split(".")[-1]]
            target = None
            for k in dict.fromkeys(tries):
                cand = name_index.get(k)
                if not cand:
                    continue
                if len(cand) == 1:
                    target = next(iter(cand))
                elif cur_mod:
                    narrow = [t for t in cand if _file_module(t.split(":", 2)[1]).startswith(cur_mod)]
                    target = narrow[0] if len(narrow) == 1 else None
                break
            if target and ("Documents", cid, target) not in seen:
                edges.append({"type": "Documents", "source": cid, "target": target})
                seen.add(("Documents", cid, target))

        for cid, ref in r["pending_refs"]:
            m = re.search(r"<([^<>]+)>$", ref.strip())  # :doc:`text <target>`
            ref = (m.group(1) if m else ref).strip().lstrip("/")
            base = re.sub(r"\.(rst|txt|md)$", "", ref)
            cands = []
            for e in (".rst", ".txt", ".md"):
                cands.append(f"doc:{base}{e}")
                cands += [f"doc:{d}/{base}{e}" for d in _DOC_DIR_CANDIDATES if not base.startswith(f"{d}/")]
            for tgt in cands:
                if tgt in doc_ids:
                    if ("References", cid, tgt) not in seen:
                        edges.append({"type": "References", "source": cid, "target": tgt})
                        seen.add(("References", cid, tgt))
                    break

    return edges


def extract_docs(repo_path: str, code_nodes: list[dict]) -> dict:
    """
    Chạy toàn bộ lớp doc cho một repo.

    Returns:
        dict gồm nodes, edges (HasChunk + Documents + References) và stats
        (số file, chunk, tham chiếu chờ, cạnh Documents đã nối, References).
    """
    files = get_doc_files(repo_path)
    results = [r for r in (DocExtractor(f, repo_path).extract() for f in files) if r]
    nodes = [n for r in results for n in r["nodes"]]
    edges = [e for r in results for e in r["edges"]]
    cross = resolve_doc_links(results, build_name_index(code_nodes))
    n_pending = sum(len(r["pending_links"]) for r in results)
    n_documents = sum(1 for e in cross if e["type"] == "Documents")
    return {
        "nodes": nodes,
        "edges": edges + cross,
        "stats": {
            "doc_files": len(files),
            "chunks": sum(1 for n in nodes if n["labels"][0] == "DocChunk"),
            "pending_links": n_pending,
            "documents_edges": n_documents,
            "references_edges": sum(1 for e in cross if e["type"] == "References"),
        },
    }
