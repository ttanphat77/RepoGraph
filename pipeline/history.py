# =============================================================================
# pipeline/history.py - Lớp history và hai nguồn HIST
#
# Lớp history (mục 6.1 pipeline_design.md):
#   Đơn vị là commit trên nhánh chính (git log --first-parent) trong HIST_YEARS năm
#   trước HEAD. Mỗi đơn vị lưu sha, cha thứ nhất, thời điểm, message đầy đủ và touch set
#   (hàm/lớp mà commit sửa, tính bằng oracle trên git diff -U0 với cha thứ nhất).
#   → {index_dir}/history/history.jsonl. Build lại chỉ tính commit mới.
#
# Chỉ mục hunk (mục 6.2): mỗi hunk của git diff -U3 -w (file .py có trong graph, bỏ hunk
#   chỉ đổi comment) được gán cho hàm/lớp mà nó đổi. → {index_dir}/history/hunks.jsonl.
#
# LocusIndex (mục 6.3, 6.4): Locus (Wen, Wu, Cheung, ASE 2016) ở mức hàm/lớp.
#   score(b, f) = max_{h ∈ H(f)} {NL(b, h) + α·CE(b, h)} + β1·Fix(f)
#   NL, CE: cosine, trọng số w = (log f + 1)·log(N / n_t).  α = min(1, λ·#tên code / #token).
#   Fix(f) = Σ 1 / (1 + e^(−12·t + 12)) trên commit sửa lỗi (message khớp fix|bug) đã sửa f.
#
# MsgIndex (mục 6b): HIST theo phần lời của commit.
#   text(c) = message + tiêu đề và mô tả của ticket/PR liên kết (links, có từ nguồn ISSUE).
#   s(c) = RRF(k = 60) của danh sách cosine TF-IDF và danh sách nối AST (hạng AST tốt nhất
#   của hàm/lớp mà c sửa). score(f) = max s(c). Pool bằng chứng = EVID_POOL_N commit đầu.
#
# Ở chế độ live (HEAD), mọi đơn vị đều là tổ tiên của HEAD vì lấy từ git log của HEAD,
# và mốc thời gian của query là lúc hỏi.
# =============================================================================

from __future__ import annotations

import functools
import hashlib
import json
import keyword
import logging
import math
import re
import subprocess
import time
from collections import Counter
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import unidiff
from nltk.stem.porter import PorterStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

import config
from pipeline.doc_extractor import _file_module
from pipeline.oracle import _src_path, changed_lines, file_nodes_at, get_oracle
from pipeline.ranking import tokenize_code
from pipeline.repo_manager import filter_source_files

logger = logging.getLogger(__name__)

_FC = ("Function", "Class")
_YEAR = 365 * 86400
_BUGFIX_RE = re.compile(r"fix|bug", re.I)                                   # AmaLgam, quy tắc 1 (A2)
_NL_STOP = set(ENGLISH_STOP_WORDS) | {k.lower() for k in keyword.kwlist}   # stop word + từ khóa Python
_stem = functools.lru_cache(maxsize=None)(PorterStemmer().stem)
_IDENT_RE = re.compile(r"`[^`\n]+`|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\(?")
_NAME_RE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*")
_LOCUS_MSG_CHARS = 2000   # độ dài message trong tài liệu Locus (hist-build của notebook cắt ở đây)
_COUNTS_VERSION = 1       # đổi khi cách tách từ đổi, để cache ma trận đếm cũ không được dùng


# ── Git ──────────────────────────────────────────────────────────────────────
def git_text(repo_path: str, *args: str) -> str:
    """stdout của git. Đọc bytes, chỉ đổi CRLF thành LF: text=True đổi cả CR đứng riêng thành
    xuống dòng, làm một dòng của diff tách làm hai và unidiff báo lỗi."""
    out = subprocess.run(["git", "-C", str(repo_path), *args], capture_output=True).stdout
    return out.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _in_graph(rel: str) -> bool:
    """File .py qua được bộ lọc của graph (không nằm trong tests, docs, ...)."""
    return rel.endswith(".py") and bool(filter_source_files([rel]))


def history_units(repo_path: str, head: str = "HEAD", years: int = config.HIST_YEARS) -> list[tuple]:
    """
    Commit trên nhánh chính từ head lùi tới `years` năm trước thời điểm của head.
    Commit gốc (không có cha) bị bỏ vì không có diff với cha.

    Returns:
        [(sha, cha thứ nhất, thời điểm commit, message đầy đủ, là merge)], mới trước cũ sau.
    """
    head_t = int(git_text(repo_path, "log", "-1", "--format=%ct", head).strip())
    since = head_t - years * _YEAR
    # -z: commit ngăn bằng NUL. Message có thể chứa 0x1e, nên không dùng 0x1e để ngăn.
    log = git_text(repo_path, "log", "-z", "--first-parent", f"--since=@{since}",
                   "--format=%H%x1f%P%x1f%ct%x1f%B", head)
    units = []
    for rec in log.split("\0"):
        rec = rec.strip("\n")
        if rec:
            h, parents, ct, msg = rec.split("\x1f", 3)
            if parents:
                units.append((h, parents.split()[0], int(ct), msg.strip(), len(parents.split()) > 1))
    return units


def _unit_record(repo_path: str, h: str, p: str, t: int, msg: str, merge: bool) -> dict:
    """Touch set của một commit: hàm/lớp (id theo tên file mới) và file có dòng đổi ngoài mọi hàm/lớp."""
    diff = git_text(repo_path, "diff", "-U0", p, h, "--", "*.py")
    changed, _ = changed_lines(diff) if diff else ({}, set())
    nodes, mods = [], set()
    for rel, lines in changed.items():
        if not _in_graph(rel):
            continue
        fn = file_nodes_at(repo_path, p, rel)              # node của file tại commit cha
        nodes += fn
        spans = [(n["start_line"], n["end_line"]) for n in fn if n["label"] in _FC and n.get("start_line")]
        if any(not any(a <= L <= b for a, b in spans) for L in lines):
            mods.add(rel)
    lab = {n["id"]: n["label"] for n in nodes}
    orc = get_oracle(diff, nodes) if nodes else {"nodes": set(), "renames": {}}
    ren = orc["renames"]
    touch = sorted(ren[k.split(":", 1)[0]] + ":" + k.split(":", 1)[1] if k.split(":", 1)[0] in ren else k
                   for k in orc["nodes"] if lab.get(k) in _FC)
    return {"h": h, "p": p, "t": t, "merge": merge, "msg": msg, "touch": touch, "touch_mod": sorted(mods)}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_history(repo_path: str, index_dir: str | Path, head: str = "HEAD") -> tuple[list[dict], dict]:
    """
    Lớp history của repo tại head. Commit đã có trong history.jsonl được dùng lại.

    Returns:
        (danh sách bản ghi commit, mới trước cũ sau; stats)
    """
    t0 = time.perf_counter()
    path = Path(index_dir) / "history" / "history.jsonl"
    old = {r["h"]: r for r in _read_jsonl(path)}
    units = history_units(repo_path, head)
    rows, n_new = [], 0
    for h, p, t, msg, merge in units:
        r = old.get(h)
        if r is None:
            r = _unit_record(repo_path, h, p, t, msg, merge)
            n_new += 1
        rows.append(r)
    _write_jsonl(path, rows)
    return rows, {"commits": len(rows), "new": n_new, "reused": len(rows) - n_new,
                  "with_touch": sum(bool(r["touch"]) for r in rows),
                  "seconds": round(time.perf_counter() - t0, 1)}


def _comment_only(h) -> bool:
    return all(not t or t.startswith("#") for t in (ln.value.strip() for ln in h if ln.is_added or ln.is_removed))


def build_hunks(repo_path: str, index_dir: str | Path, units: list[dict]) -> tuple[list[dict], dict]:
    """
    Chỉ mục hunk của các commit có touch khác rỗng. Mỗi hunk:
    {"u": sha, "f": file (tên sau đổi tên), "k": thứ tự trong file, "ids": hàm/lớp mà hunk đổi, "text": hunk}.
    Commit đã xử lý (ghi trong hunks_done.json, kể cả commit không cho hunk nào, vd chỉ đổi comment)
    được dùng lại, không tính lại.
    """
    t0 = time.perf_counter()
    path = Path(index_dir) / "history" / "hunks.jsonl"
    done_path = path.with_name("hunks_done.json")
    old: dict[str, list[dict]] = {}
    for r in _read_jsonl(path):
        old.setdefault(r["u"], []).append(r)
    done = set(json.loads(done_path.read_text(encoding="utf-8"))) if done_path.exists() else set(old)
    rows, n_new = [], 0
    for u in units:
        if not u["touch"]:
            continue
        if u["h"] in done:
            rows += old.get(u["h"], [])
            continue
        n_new += 1
        diff = git_text(repo_path, "diff", "-U3", "-w", u["p"], u["h"], "--", "*.py")
        if not diff:
            continue
        for pf in unidiff.PatchSet(diff):
            src = _src_path(pf)
            if pf.is_added_file or not _in_graph(src):
                continue
            nodes = file_nodes_at(repo_path, u["p"], src)
            if not nodes:
                continue
            lab = {x["id"]: x["label"] for x in nodes}
            for k, h in enumerate(pf):
                if _comment_only(h):
                    continue
                one = f"--- a/{src}\n+++ b/{pf.path}\n{h}"
                ids = sorted(pf.path + x[len(src):] for x in get_oracle(one, nodes)["nodes"] if lab.get(x) in _FC)
                rows.append({"u": u["h"], "f": pf.path, "k": k, "ids": ids, "text": str(h)})
    _write_jsonl(path, rows)
    done_path.write_text(json.dumps(sorted(u["h"] for u in units if u["touch"])), encoding="utf-8")
    return rows, {"hunks": len(rows), "new_commits": n_new, "seconds": round(time.perf_counter() - t0, 1)}


# ── Văn bản và TF-IDF (Locus (1)–(4)) ────────────────────────────────────────
def nl_terms(txt: str) -> list[str]:
    """Token NL: tách định danh (camelCase, snake_case), bỏ stop word và từ khóa Python, Porter."""
    return [_stem(t) for t in tokenize_code(txt) if t not in _NL_STOP]


def code_terms(txt: str) -> list[str]:
    """
    Từ giống code (A7), giữ nguyên không tách: có "_" hoặc ".", có chữ hoa sau ký tự đầu,
    nằm trong backtick, hoặc đứng ngay trước "(". Từ có dấu chấm cho thêm từng phần:
    "QuerySet.filter" → "QuerySet.filter", "QuerySet", "filter".
    """
    out = []
    for m in _IDENT_RE.finditer(txt):
        t = m.group(0)
        if t.startswith("`"):
            toks = _NAME_RE.findall(t)
        else:
            call, t = t.endswith("("), t.rstrip("(")
            toks = [t] if call or "_" in t or "." in t or any(c.isupper() for c in t[1:]) else []
        for x in toks:
            out.append(x)
            if "." in x:
                out.extend(x.split("."))
    return out


def hunk_body(text: str) -> str:
    """Nội dung hunk (ngữ cảnh, dòng xóa, dòng thêm), bỏ dòng tiêu đề @@ và ký tự đầu dòng."""
    return "\n".join(l[1:] for l in text.split("\n")[1:])


def term_counts(docs: list[str], fn, cache_path: Path | None = None) -> tuple[sp.csr_matrix, dict[str, int]]:
    """
    Ma trận đếm (hàng = tài liệu, cột = từ) và từ điển cột.

    Với cache_path (file .npz): dùng lại ma trận đã lưu khi khóa trùng. Khóa là sha1 của
    _COUNTS_VERSION, tên hàm tách từ và toàn văn các tài liệu, nên tài liệu đổi thì tính lại.
    """
    key = meta = None
    if cache_path is not None:
        h = hashlib.sha1(f"{_COUNTS_VERSION}:{fn.__name__}".encode("utf-8"))
        for d in docs:
            h.update(b"\0" + d.encode("utf-8"))
        key, meta = h.hexdigest(), cache_path.with_suffix(".json")
        if cache_path.exists() and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            if m.get("key") == key:
                return sp.load_npz(cache_path).tocsr(), m["vocab"]
    vocab, r, c, v = {}, [], [], []
    for i, d in enumerate(docs):
        for t, k in Counter(fn(d)).items():
            r.append(i); c.append(vocab.setdefault(t, len(vocab))); v.append(k)
    X = sp.csr_matrix((v, (r, c)), shape=(len(docs), len(vocab)), dtype=np.float64)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        sp.save_npz(cache_path, X)
        meta.write_text(json.dumps({"key": key, "vocab": vocab}, ensure_ascii=False), encoding="utf-8")
    return X, vocab


def tfidf(X: sp.spmatrix) -> tuple[sp.csr_matrix, np.ndarray]:
    """Locus (2): w = (log f + 1)·log(N / n_t), N và n_t tính trên các tài liệu đưa vào; hàng chuẩn hóa L2."""
    X = X.tocsr().copy()
    X.eliminate_zeros()
    N = X.shape[0]
    df = np.bincount(X.indices, minlength=X.shape[1])
    idf = np.zeros(X.shape[1])
    nz = df > 0
    idf[nz] = np.log(N / df[nz])
    W = X.copy()
    W.data = np.log(W.data) + 1.0
    W = (W @ sp.diags(idf)).tocsr()
    norm = np.sqrt(np.asarray(W.power(2).sum(axis=1)).ravel())
    norm[norm == 0] = 1.0
    return (sp.diags(1.0 / norm) @ W).tocsr(), idf


def qvec(terms: list[str], vocab: dict[str, int], idf: np.ndarray) -> np.ndarray:
    """Vector query theo cùng trọng số, chuẩn hóa L2. Từ không có trong vocab bị bỏ."""
    v = np.zeros(len(idf))
    for t, k in Counter(terms).items():
        j = vocab.get(t)
        if j is not None:
            v[j] = (math.log(k) + 1.0) * idf[j]
    n = np.linalg.norm(v)
    return v / n if n else v


def graph_names(nodes: list[dict]) -> set[str]:
    """Tên dùng cho CE: tên lớp và hàm, cùng tên module dạng chấm như người viết issue dùng
    (src/flask/app.py → flask.app; bỏ tiền tố src. như lớp doc)."""
    out = {n["name"] for n in nodes if n["label"] in _FC and n.get("name")}
    for n in nodes:
        path = n.get("file") or n.get("name") or ""
        if n["label"] == "Module" and path.endswith(".py"):
            out.add(_file_module(path))
    return out


def _top_functions(sc: np.ndarray, keys: list[str], keep: np.ndarray, prefix: str, top: int) -> list[dict]:
    """Hàm/lớp có điểm > 0 và có trong graph, xếp theo điểm giảm dần rồi theo id, tối đa top."""
    sc = np.where(keep, sc, 0.0)
    order = [j for j in np.lexsort((np.array(keys), -sc)) if sc[j] > 0][:top]
    return [{"id": f"{prefix}:{keys[j]}", "score": float(sc[j])} for j in order]


# ── HIST theo Locus ──────────────────────────────────────────────────────────
class LocusIndex:
    """Locus ở mức hàm/lớp trên chỉ mục hunk của HEAD."""

    def __init__(self, units: list[dict], hunks: list[dict], graph_fc: set[str],
                 names: set[str], id_prefix: str, cache_dir: Path | None = None):
        """
        Args:
            units:     bản ghi commit (build_history).
            hunks:     bản ghi hunk (build_hunks).
            graph_fc:  id Function/Class của graph hiện tại (có tiền tố id_prefix).
            names:     tên trong graph cho CE (graph_names).
            id_prefix: tiền tố id node của graph ("local" hoặc commit).
            cache_dir: nơi lưu ma trận đếm từ (term_counts); None → không lưu.
        """
        self.prefix = id_prefix
        self.names = names
        # Tài liệu = hunk + message cắt ở _LOCUS_MSG_CHARS ký tự, như file history của notebook
        msg = {u["h"]: u["msg"][:_LOCUS_MSG_CHARS] for u in units}
        docs = [hunk_body(x["text"]) + "\n" + msg.get(x["u"], "") for x in hunks]
        Xnl, self.nl_vocab = term_counts(docs, nl_terms, cache_dir / "locus_nl.npz" if cache_dir else None)
        Xce, self.ce_vocab = term_counts(docs, code_terms, cache_dir / "locus_ce.npz" if cache_dir else None)
        self.Wnl, self.idf_nl = tfidf(Xnl)
        mask = np.zeros(len(self.ce_vocab))
        mask[[j for t, j in self.ce_vocab.items() if t in names]] = 1.0
        self.Wce, self.idf_ce = tfidf((Xce @ sp.diags(mask)).tocsr())

        fn_vocab, r, c = {}, [], []
        for i, x in enumerate(hunks):
            for k in x["ids"]:
                r.append(i); c.append(fn_vocab.setdefault(k, len(fn_vocab)))
        bf = [u for u in units if u["touch"] and _BUGFIX_RE.search(u["msg"])]
        fr, fcol = [], []
        for i, u in enumerate(bf):
            for k in u["touch"]:
                fr.append(i); fcol.append(fn_vocab.setdefault(k, len(fn_vocab)))
        nf = len(fn_vocab)
        self.keys = sorted(fn_vocab, key=fn_vocab.get)
        self.M = sp.csr_matrix((np.ones(len(r)), (r, c)), shape=(len(hunks), nf)).tocsc()
        self.F = sp.csr_matrix((np.ones(len(fr)), (fr, fcol)), shape=(len(bf), nf))
        self.bf_t = np.array([u["t"] for u in bf], dtype=np.float64)
        self.t0 = float(min((u["t"] for u in units), default=0))
        self.keep = np.array([f"{id_prefix}:{k}" in graph_fc for k in self.keys], dtype=bool)
        self.n_hunks = len(hunks)

    def rank(self, query: str, t_query: float, top: int = config.AST_DEPTH) -> dict:
        """
        Điểm Locus của mọi hàm/lớp cho query, tại thời điểm t_query (giây UNIX).

        Returns:
            {"items": [{"id", "score"}] (tối đa top, điểm > 0), "alpha", "ce_terms"}
        """
        ce_q = [t for t in code_terms(query) if t in self.names]
        alpha = min(1.0, config.LOCUS_LAMBDA * len(ce_q) / max(1, len(tokenize_code(query))))
        if not self.n_hunks:
            return {"items": [], "alpha": alpha, "ce_terms": ce_q}
        nl = self.Wnl @ qvec(nl_terms(query), self.nl_vocab, self.idf_nl)
        s = nl + alpha * (self.Wce @ qvec(ce_q, self.ce_vocab, self.idf_ce))
        best = (sp.diags(s) @ self.M).max(axis=0).toarray().ravel()      # max trên các hunk của từng hàm/lớp
        t = np.clip((self.bf_t - self.t0) / max(1.0, t_query - self.t0), 0.0, 1.0)
        fix = self.F.T @ (1.0 / (1.0 + np.exp(-12.0 * t + 12.0)))
        full = best + config.LOCUS_BETA1 * fix
        return {"items": _top_functions(full, self.keys, self.keep, self.prefix, top),
                "alpha": alpha, "ce_terms": ce_q}


# ── HIST theo phần lời của commit ────────────────────────────────────────────
class MsgIndex:
    """HIST theo phần lời: commit được xét, text(c), TF-IDF và ma trận commit × hàm/lớp."""

    def __init__(self, units: list[dict], graph_fc: set[str], id_prefix: str,
                 links: dict[str, list[dict]] | None = None, cache_dir: Path | None = None):
        """
        Args:
            units:     bản ghi commit (build_history).
            graph_fc:  id Function/Class của graph hiện tại.
            id_prefix: tiền tố id node.
            links:     sha → báo cáo liên kết [{"n", "title", "body", "pr"}] (nguồn ISSUE).
            cache_dir: nơi lưu ma trận đếm từ (term_counts); None → không lưu.
        """
        self.prefix = id_prefix
        links = links or {}
        self.units = [u for u in units
                      if u["touch"] and len(u["touch"]) <= config.HIST_MAX_TOUCH
                      and any(f"{id_prefix}:{k}" in graph_fc for k in u["touch"])]
        texts = [u["msg"] + "".join(f"\n{r['title']}\n{r['body']}" for r in links.get(u["h"], []))
                 for u in self.units]
        self.links = [sorted(int(r["n"]) for r in links.get(u["h"], [])) for u in self.units]
        X, self.vocab = term_counts(texts, nl_terms, cache_dir / "msg_nl.npz" if cache_dir else None)
        self.W, self.idf = tfidf(X)
        fn_vocab, tr, tc = {}, [], []
        for i, u in enumerate(self.units):
            for k in u["touch"]:
                tr.append(i); tc.append(fn_vocab.setdefault(k, len(fn_vocab)))
        self.keys = sorted(fn_vocab, key=fn_vocab.get)
        self.T = sp.csr_matrix((np.ones(len(tr)), (tr, tc)), shape=(len(self.units), len(fn_vocab)))
        self.keep = np.array([f"{id_prefix}:{k}" in graph_fc for k in self.keys], dtype=bool)
        self.t = np.array([u["t"] for u in self.units], dtype=np.float64)
        h = np.array([u["h"] for u in self.units])
        self.sha_r = np.argsort(np.argsort(h)) if len(h) else np.zeros(0, dtype=np.int64)

    def rank(self, query: str, ast_ids: list[str], pool_n: int = config.EVID_POOL_N,
             top: int = config.AST_DEPTH) -> dict:
        """
        s(c) = 1/(k + hạng lời) + 1/(k + hạng nối AST), commit vắng mặt ở một danh sách không
        nhận số hạng đó. Hòa trong từng danh sách: commit mới hơn trước, rồi sha.

        Returns:
            {"items": [{"id", "score"}] hàm/lớp theo max s(c),
             "pool": [{"h", "t", "s", "cos", "ast_r", "touch", "links"}] EVID_POOL_N commit đầu}
        """
        n = len(self.units)
        if not n:
            return {"items": [], "pool": []}
        cos = np.asarray(self.W @ qvec(nl_terms(query), self.vocab, self.idf)).ravel()
        big = len(ast_ids) + 1
        rk = {x: i + 1 for i, x in enumerate(ast_ids)}
        fr = np.array([rk.get(f"{self.prefix}:{k}", big) for k in self.keys], dtype=np.float64)
        best = np.minimum.reduceat(fr[self.T.indices], self.T.indptr[:-1]) if self.T.nnz \
            else np.full(n, big, dtype=np.float64)
        s = np.zeros(n)
        for v, has in ((-cos, cos > 0), (best, best < big)):
            ix = np.flatnonzero(has)
            ix = ix[np.lexsort((self.sha_r[ix], -self.t[ix], v[ix]))]
            s[ix] += 1.0 / (config.RRF_K + np.arange(1, ix.size + 1))
        sc = (sp.diags(s) @ self.T).max(axis=0).toarray().ravel()           # score(f) = max s(c)
        items = _top_functions(sc, self.keys, self.keep, self.prefix, top)
        order = [j for j in np.lexsort((self.sha_r, -self.t, -s)) if s[j] > 0][:pool_n]
        pool = [{"h": self.units[j]["h"], "t": int(self.t[j]), "s": float(s[j]), "cos": float(cos[j]),
                 "ast_r": int(best[j]) if best[j] < big else None,
                 "touch": [f"{self.prefix}:{k}" for k in self.units[j]["touch"]],
                 "links": self.links[j]} for j in order]
        return {"items": items, "pool": pool}
