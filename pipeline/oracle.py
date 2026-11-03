# =============================================================================
# pipeline/oracle.py - Oracle: một diff sửa những hàm/lớp nào
#
# Thiết kế: mục 3 pipeline_design.md (oracle đã sửa ở việc 1.1 của nghiên cứu).
# Lớp history dùng oracle để tính touch set của mỗi commit (cạnh Modifies) và gán
# hunk cho hàm/lớp (Locus). Nguồn ISSUE dùng touch set làm Fix(b′).
#
# Quy tắc:
#   1. Mỗi dòng bị xóa → hàm/lớp HẸP NHẤT chứa nó. Khoảng dòng của node tính từ
#      decorator đầu tiên.
#   2. Dòng thêm liền nhau tạo thành một khối, gán theo điểm chèn:
#      (a) khối nằm giữa thân node;
#      (b) khối nối vào cuối thân node và mọi dòng từ đầu khối tới dòng đang xét đều
#          thụt sâu hơn dòng def (gặp dòng thụt nông hơn = bắt đầu code mới);
#      (c) decorator mới ngay trên dòng def, khi mọi dòng sau nó trong khối cũng là decorator.
#      Dòng trống chỉ tính khi nằm trong thân một Function.
#   3. Class chỉ là gold khi có dòng đổi nằm trong class nhưng ngoài mọi method.
#   4. File chỉ đổi ở cấp module → node Module của file.
#   5. File đổi tên: dòng gốc thuộc file ở tên CŨ; renames = {tên cũ: tên mới}.
#
# Node ở dạng phẳng: {"id", "label", "name", "file", "start_line", "end_line",
# "deco_start", "indent"}. Id không có tiền tố commit: "path:Class:method".
# =============================================================================

from __future__ import annotations

import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

import unidiff

from pipeline.ast_engine import ASTEngine
from pipeline.languages.python import python_extractor
from pipeline.schemas import load_schema

_FC = ("Function", "Class")


def _src_path(pf) -> str:
    """Đường dẫn file ở bản GỐC. unidiff `path` trả tên MỚI khi file đổi tên."""
    s = pf.source_file or ""
    if s.startswith("a/"):
        s = s[2:]
    return pf.path if (pf.is_added_file or s in ("", "/dev/null")) else s


def changed_lines(patch_text: str) -> tuple[dict[str, set[int]], set[str]]:
    """
    Dòng ở bản gốc bị đổi, theo file. Dòng xóa → số dòng gốc. Dòng thêm → dòng gốc ngay
    trước điểm chèn. File mới tạo tách riêng.

    Returns:
        ({đường dẫn gốc: {số dòng}}, {file mới tạo})
    """
    out, added_files = {}, set()
    for pf in unidiff.PatchSet(patch_text):
        if pf.is_added_file:
            added_files.add(pf.path)
            continue
        lines = out.setdefault(_src_path(pf), set())
        for h in pf:
            last = None
            for ln in h:
                if ln.is_removed:
                    lines.add(ln.source_line_no)
                    last = ln.source_line_no
                elif ln.is_context:
                    last = ln.source_line_no
                elif ln.is_added:
                    lines.add(last if last is not None else h.source_start)
    return out, added_files


def patch_changes(patch_text: str) -> tuple[dict, dict[str, str], set[str]]:
    """
    Như changed_lines nhưng giữ riêng dòng xóa và các khối dòng thêm.

    Khối = các dòng thêm liền nhau, cùng điểm chèn (dòng gốc ngay trước, dòng gốc ngay sau).
    Mỗi dòng trong khối là (độ thụt lề, nội dung); dòng trống có độ thụt lề None.
    Hunk chèn thuần "-L,0" nghĩa là chèn sau dòng L.

    Returns:
        ({đường dẫn gốc: {"removed": {dòng}, "inserts": [(trước, sau, [(thụt lề, text)])]}},
         renames {tên cũ: tên mới}, {file mới tạo})
    """
    out, renames, added_files = {}, {}, set()
    for pf in unidiff.PatchSet(patch_text):
        if pf.is_added_file:
            added_files.add(pf.path)
            continue
        src = _src_path(pf)
        if src != pf.path:
            renames[src] = pf.path
        rec = out.setdefault(src, {"removed": set(), "inserts": []})
        for h in pf:
            hl, last, blk = list(h), None, None
            for i, ln in enumerate(hl):
                if not ln.is_added:
                    blk = None
                if ln.is_removed:
                    rec["removed"].add(ln.source_line_no)
                    last = ln.source_line_no
                elif ln.is_context:
                    last = ln.source_line_no
                elif ln.is_added:
                    if blk is None:
                        nxt = next((x.source_line_no for x in hl[i + 1:] if not x.is_added), None)
                        if h.source_length == 0:
                            prev = last if last is not None else h.source_start
                        else:
                            prev = last if last is not None else h.source_start - 1
                        blk = (prev, nxt if nxt is not None else prev + 1, [])
                        rec["inserts"].append(blk)
                    text = ln.value.rstrip("\n")
                    blk[2].append((len(text) - len(text.lstrip(" \t")) if text.strip() else None, text))
    return out, renames, added_files


def get_oracle(patch_text: str, nodes: list[dict]) -> dict:
    """
    Hàm/lớp (hoặc Module) mà diff sửa, theo các quy tắc ở đầu file.

    Args:
        patch_text: diff dạng unified.
        nodes:      node phẳng của các file bị sửa, tại bản GỐC (file_nodes_at).

    Returns:
        {"nodes": {id}, "files_code", "added_files", "unreachable", "module_only", "renames"}
    """
    changed, renames, added_files = patch_changes(patch_text)
    by_file = defaultdict(list)
    module_of = {n["name"]: n["id"] for n in nodes if n["label"] == "Module"}   # name = path file
    for n in nodes:
        if n["label"] in _FC and n.get("start_line") and n.get("end_line"):
            by_file[n["file"]].append(n)
    start = lambda n: n.get("deco_start") or n["start_line"]
    narrow = lambda c: min(c, key=lambda n: (n["end_line"] - start(n), n["id"]))
    gold, module_only = set(), set()
    for f, rec in changed.items():
        if not f.endswith(".py"):
            continue
        fnodes, hit = by_file[f], False
        for L in rec["removed"]:
            inner = [n for n in fnodes if start(n) <= L <= n["end_line"]]
            if inner:
                gold.add(narrow(inner)["id"])
                hit = True
        for a, b, blk in rec["inserts"]:
            if not (fnodes and all("indent" in n for n in fnodes)):
                # Node không có thông tin thụt lề → gán theo dòng trước, rồi dòng sau
                cand = [n for n in fnodes if start(n) <= a <= n["end_line"]] or \
                       [n for n in fnodes if start(n) <= b <= n["end_line"]]
                if cand:
                    gold.add(narrow(cand)["id"])
                    hit = True
                continue
            inside = [n for n in fnodes if start(n) <= a and b <= n["end_line"]]
            tail = [n for n in fnodes if n["end_line"] == a]
            head = [n for n in fnodes if start(n) == b]
            low = None  # thụt lề nhỏ nhất từ đầu khối tới dòng đang xét
            for i, (d, text) in enumerate(blk):
                if d is None:
                    cand = [n for n in inside if n["label"] == "Function"]
                else:
                    low = d if low is None else min(low, d)
                    cand = inside + [n for n in tail if low > n["indent"]]
                    if text.lstrip().startswith("@") and all(
                            t.lstrip().startswith("@") for x, t in blk[i:] if x is not None):
                        cand += [n for n in head if d == n["indent"]]
                if cand:
                    gold.add(narrow(cand)["id"])
                    hit = True
        if (rec["removed"] or rec["inserts"]) and not hit:
            module_only.add(f)
            if f in module_of:
                gold.add(module_of[f])
    files_code = {f for f in changed if f.endswith(".py")}
    graph_files = {n["file"] for n in nodes if n.get("file")}
    return {"nodes": gold,
            "files_code": files_code,
            "added_files": {f for f in added_files if f.endswith(".py")},
            "unreachable": files_code - graph_files,
            "module_only": module_only,
            "renames": renames}


def file_nodes_from_source(rel: str, data: bytes) -> list[dict]:
    """
    Node phẳng của một file Python (nội dung data, đường dẫn rel), parse bằng ASTEngine
    với schema simple. Function/Class có thêm deco_start (dòng decorator đầu tiên, hoặc
    dòng def) và indent (độ thụt lề của dòng def/class).
    """
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        r = ASTEngine(str(p), td, "X", load_schema("simple"), python_extractor).parse()
    deco, stack = {}, [python_extractor.parser.parse(data).root_node]   # dòng def → dòng decorator đầu
    while stack:
        t = stack.pop()
        if t.type == "decorated_definition" and t.child_by_field_name("definition") is not None:
            deco[t.child_by_field_name("definition").start_point[0] + 1] = t.start_point[0] + 1
        stack.extend(t.children)
    lines = data.decode("utf-8", errors="replace").split("\n")
    out = []
    for n in (r or {}).get("nodes", []):
        pr = n["properties"]
        label = n["labels"][0]
        nd = {"id": n["id"].split(":", 1)[1], "label": label, "name": pr.get("name", ""),
              "file": pr.get("file") or (pr.get("name", "") if label == "Module" else ""),
              "start_line": pr.get("start_line"), "end_line": pr.get("end_line")}
        s = nd["start_line"]
        if label in _FC and s and s <= len(lines):
            nd["deco_start"] = deco.get(s, s)
            nd["indent"] = len(lines[s - 1]) - len(lines[s - 1].lstrip(" \t"))
        out.append(nd)
    return out


def file_nodes_at(repo_path: str, commit: str, rel: str) -> list[dict]:
    """Node phẳng của file rel tại commit (git show). File không tồn tại tại commit → []."""
    data = subprocess.run(["git", "-C", str(repo_path), "show", f"{commit}:{rel}"],
                          capture_output=True).stdout
    return file_nodes_from_source(rel, data) if data else []
