# =============================================================================
# pipeline/issues.py - Nguồn ISSUE: báo cáo lỗi cũ đã sửa (GitHub)
#
# Thiết kế: mục 7 pipeline_design.md.
#
# Tải (fetch_reports): issue và PR đã đóng qua /repos/<owner>/<repo>/issues?state=closed,
#   phân trang theo link "next" (con trỏ). → {index_dir}/issues/reports.jsonl.
#   Tải dở (hết lượt gọi) → phần đã tải ở reports.jsonl.part, link kế tiếp ở .next;
#   lần sau đi tiếp. Đã có file → chỉ tải mục cập nhật từ lần tải trước (tham số since).
#
# Liên kết (issue_links): báo cáo ↔ commit trên nhánh chính, mọi cặp là loại "fixed".
#   - từ khóa đóng issue của GitHub (close, fix, resolve và các dạng chia) trong message;
#   - từ khóa đóng issue trong body của PR của commit: merge commit "Merge pull request #PR",
#     hoặc commit squash có "(#PR)" ở cuối dòng đầu.
#   Từ khóa chỉ nhận số issue của chính repo: "#N", "<owner>/<repo>#N" hoặc URL issue của repo.
#
# IssueIndex: SimiScore của BugLocator (Zhou, Zhang, Lo, ICSE 2012).
#   SimiScore(f) = Σ sim(b, b′) / |Fix(b′)| trên báo cáo cũ b′ có f ∈ Fix(b′).
#   sim = cosine TF-IDF (TfidfTransformer, sublinear_tf) giữa query và title + body của b′.
#   Fix(b′) = hợp touch set của các commit đã nối với b′. Báo cáo có Fix(b′) rỗng không đóng góp.
#   Pool bằng chứng = EVID_POOL_N báo cáo có sim cao nhất, sim > 0 và Fix(b′) khác rỗng.
#
# Chế độ live (HEAD): mốc cắt thời gian là lúc hỏi, không lọc báo cáo của chính prompt.
# =============================================================================

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfTransformer

import config
from pipeline.history import _read_jsonl, _stem, _top_functions, _write_jsonl, term_counts
from pipeline.ranking import tokenize_code

logger = logging.getLogger(__name__)

_GH_PAGE = 100
_MERGE_RE = re.compile(r"Merge pull request #(\d+)")
_SQUASH_RE = re.compile(r"\(#(\d+)\)\s*$")          # dòng đầu của commit squash: "Fix X (#12345)"
_GH_REMOTE_RE = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$")


class RateLimited(Exception):
    """GitHub hết lượt gọi. reset = thời điểm (Unix) GitHub mở lại."""

    def __init__(self, reset: float | None):
        super().__init__(f"GitHub rate limit, reset at {reset}")
        self.reset = reset


def github_slug(remote: str | None) -> str | None:
    """'https://github.com/pallets/flask(.git)' hoặc 'git@github.com:pallets/flask.git' → 'pallets/flask'."""
    m = _GH_REMOTE_RE.search(remote or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


# ── Tải ──────────────────────────────────────────────────────────────────────
def _http(url: str, token: str = "") -> tuple[str | None, dict]:
    """GET một trang. Thử lại khi lỗi mạng hoặc lỗi máy chủ. Hết lượt gọi → RateLimited."""
    headers = {"User-Agent": "repograph", "Accept": "application/vnd.github+json",
               **({"Authorization": f"Bearer {token}"} if token else {})}
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", errors="replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, {}
            if rate_limited(e.code, e.headers):
                reset = e.headers.get("X-RateLimit-Reset")
                raise RateLimited(float(reset) if reset else None)
            if e.code < 500:
                raise                                   # vd 403 vì thiếu quyền: báo lỗi thật, không chờ
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"cannot fetch {url}")


def rate_limited(code: int, headers) -> bool:
    """
    GitHub hết lượt gọi: 429, hoặc 403 có X-RateLimit-Remaining = 0 (giới hạn chính)
    hoặc có Retry-After (giới hạn phụ). 403 khác (thiếu quyền, repo bị chặn) không phải hết lượt.
    """
    if code == 429:
        return True
    return code == 403 and (headers.get("X-RateLimit-Remaining") == "0" or headers.get("Retry-After") is not None)


def _iso(ts: str) -> int:
    return int(datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp())


def gh_rows(text: str) -> list[dict]:
    """Một trang JSON của GitHub → bản ghi báo cáo {n, pr, title, body, created, url}."""
    return [{"n": it["number"], "pr": "pull_request" in it, "title": it.get("title") or "",
             "body": it.get("body") or "", "created": _iso(it["created_at"]), "url": it.get("html_url", "")}
            for it in json.loads(text)]


def fetch_reports(slug: str, index_dir: str | Path, token: str = config.GITHUB_TOKEN,
                  http=_http) -> dict:
    """
    Tải issue và PR đã đóng của repo GitHub `slug` vào {index_dir}/issues/reports.jsonl.

    Returns:
        {"complete": bool, "reports": số báo cáo trong file chính, "new_rows": số mục vừa tải,
         "pages": số trang vừa tải, "reset": thời điểm GitHub mở lại khi complete = False}
    """
    d = Path(index_dir) / "issues"
    d.mkdir(parents=True, exist_ok=True)
    path, part, nxt, st_path = d / "reports.jsonl", d / "reports.jsonl.part", d / "reports.jsonl.next", \
        d / "fetch_state.json"
    state = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
    base = (f"https://api.github.com/repos/{slug}/issues?state=closed&per_page={_GH_PAGE}"
            "&sort=created&direction=asc")
    if part.exists() and nxt.exists() and nxt.read_text(encoding="utf-8").strip():
        url = nxt.read_text(encoding="utf-8").strip()           # đi tiếp lần tải dở
        started = state.get("started_at")
    else:
        part.write_text("", encoding="utf-8")
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = base + (f"&since={state['fetched_at']}" if path.exists() and state.get("fetched_at") else "")
        st_path.write_text(json.dumps({**state, "started_at": started}), encoding="utf-8")
    pages = new_rows = 0
    try:
        while url:
            text, h = http(url, token)
            rows = gh_rows(text) if text else []
            with open(part, "a", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
            m = re.search(r'<([^>]+)>;\s*rel="next"', h.get("Link") or h.get("link") or "")
            url = m.group(1) if m and rows else None
            nxt.write_text(url or "", encoding="utf-8")
            pages += 1
            new_rows += len(rows)
    except RateLimited as e:
        logger.warning(f"GitHub rate limit after {pages} pages; the next build continues from {nxt}.")
        return {"complete": False, "reports": len(_read_jsonl(path)), "new_rows": new_rows,
                "pages": pages, "reset": e.reset}

    rows = {r["n"]: r for r in _read_jsonl(path)}
    for r in _read_jsonl(part):
        rows[r["n"]] = r                                         # mục cập nhật: giữ bản mới nhất
    _write_jsonl(path, [r for _, r in sorted(rows.items())])
    part.unlink()
    nxt.unlink(missing_ok=True)
    st_path.write_text(json.dumps({"fetched_at": started}), encoding="utf-8")
    return {"complete": True, "reports": len(rows), "new_rows": new_rows, "pages": pages, "reset": None}


# ── Liên kết báo cáo ↔ commit ────────────────────────────────────────────────
def gh_close_re(slug: str) -> re.Pattern:
    """Từ khóa đóng issue của GitHub, chỉ nhận số issue của chính repo."""
    r = re.escape(slug)
    return re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b\s*:?\s*"
                      rf"(?:https?://github\.com/{r}/issues/|{r}#|#)(\d+)", re.I)


def pr_of(msg: str) -> int | None:
    """Số PR của commit: "Merge pull request #N" ở đầu message, hoặc "(#N)" ở cuối dòng đầu (squash)."""
    m = _MERGE_RE.match(msg) or _SQUASH_RE.search(msg.split("\n", 1)[0])
    return int(m.group(1)) if m else None


def issue_links(units: list[dict], reports: list[dict], slug: str) -> dict[tuple[int, str], str]:
    """{(số báo cáo, sha commit): "fixed"} từ message của commit và body của PR của commit."""
    pr_body = {r["n"]: r["body"] for r in reports if r["pr"]}
    close = gh_close_re(slug)
    out = {}
    for u in units:
        ns = {int(n) for n in close.findall(u["msg"])}
        pr = pr_of(u["msg"])
        if pr is not None:
            ns |= {int(n) for n in close.findall(pr_body.get(pr, ""))}
        for n in ns:
            out[(n, u["h"])] = "fixed"
    return out


def commit_texts(units: list[dict], reports: list[dict], links: dict) -> dict[str, list[dict]]:
    """
    Báo cáo liên kết của từng commit cho phần lời của HIST (mục 6b): issue (không phải PR)
    mà commit đóng, và PR của chính commit.
    """
    rep = {r["n"]: r for r in reports}
    out: dict[str, list[dict]] = defaultdict(list)
    for (n, h), ty in sorted(links.items()):
        if ty == "fixed" and n in rep and not rep[n]["pr"]:
            out[h].append(rep[n])
    for u in units:
        pr = pr_of(u["msg"])
        if pr is not None and rep.get(pr, {}).get("pr"):
            out[u["h"]].append(rep[pr])
    return dict(out)


# ── SimiScore ────────────────────────────────────────────────────────────────
def issue_terms(txt: str) -> list[str]:
    """Token của báo cáo và của query: tách định danh, bỏ stop word tiếng Anh, Porter."""
    return [_stem(t) for t in tokenize_code(txt) if t not in ENGLISH_STOP_WORDS]


class IssueIndex:
    """BugLocator SimiScore trên các báo cáo đã đóng (không tính PR)."""

    def __init__(self, reports: list[dict], units: list[dict], links: dict[tuple[int, str], str],
                 graph_fc: set[str], id_prefix: str):
        self.prefix = id_prefix
        self.docs = [r for r in reports if not r["pr"]]
        pos = {r["n"]: j for j, r in enumerate(self.docs)}
        X, self.vocab = term_counts([r["title"] + "\n" + r["body"] for r in self.docs], issue_terms)
        # Không báo cáo nào, hoặc báo cáo không có từ nào sau khi lọc stopword → không xếp hạng
        self.tr = TfidfTransformer(sublinear_tf=True).fit(X) if X.shape[0] and X.shape[1] else None
        self.W = self.tr.transform(X) if self.tr is not None else X
        touch = {u["h"]: u["touch"] for u in units}
        fn_vocab, r, c, ty_of = {}, [], [], defaultdict(set)
        for (n, h), ty in sorted(links.items()):
            if n in pos and touch.get(h):
                ty_of[pos[n]].add(ty)
                for k in touch[h]:
                    r.append(pos[n]); c.append(fn_vocab.setdefault(k, len(fn_vocab)))
        self.keys = sorted(fn_vocab, key=fn_vocab.get)
        R = sp.csr_matrix((np.ones(len(r)), (r, c)), shape=(len(self.docs), len(fn_vocab)))
        R.data[:] = 1.0                                   # commit khác nhau sửa cùng hàm/lớp chỉ tính 1 lần
        self.R = R
        self.nfix = np.asarray(R.sum(axis=1)).ravel()
        self.links = ty_of
        self.keep = np.array([f"{id_prefix}:{k}" in graph_fc for k in self.keys], dtype=bool)

    def rank(self, query: str, pool_n: int = config.EVID_POOL_N, top: int = config.AST_DEPTH) -> dict:
        """
        Returns:
            {"items": [{"id", "score"}] hàm/lớp theo SimiScore,
             "pool": [{"n", "cos", "title", "body", "created", "url", "fix", "links"}] báo cáo có sim cao nhất}
        """
        if not len(self.docs) or self.tr is None:
            return {"items": [], "pool": []}
        qc = Counter(t for t in issue_terms(query) if t in self.vocab)
        q = sp.csr_matrix((list(qc.values()), ([0] * len(qc), [self.vocab[t] for t in qc])),
                          shape=(1, len(self.vocab)))
        sims = (self.W @ self.tr.transform(q).T).toarray().ravel()
        elig = self.nfix > 0
        sc = self.R.T @ np.where(elig, sims / np.maximum(self.nfix, 1.0), 0.0)
        items = _top_functions(sc, self.keys, self.keep, self.prefix, top)
        cand = [j for j in np.argsort(-np.where(elig, sims, -1.0), kind="stable")[:pool_n]
                if elig[j] and sims[j] > 0]
        pool = [{"n": self.docs[j]["n"], "cos": float(sims[j]), "title": self.docs[j]["title"],
                 "body": self.docs[j]["body"], "created": self.docs[j]["created"],
                 "url": self.docs[j].get("url", ""),
                 "fix": sorted(f"{self.prefix}:{self.keys[k]}"
                               for k in self.R.indices[self.R.indptr[j]:self.R.indptr[j + 1]]),
                 "links": sorted(self.links[j])} for j in cand]
        return {"items": items, "pool": pool}


def load_issue_data(index_dir: str | Path) -> tuple[list[dict], dict[tuple[int, str], str]]:
    """Báo cáo và liên kết đã lưu ở {index_dir}/issues/. Chưa tải → ([], {})."""
    d = Path(index_dir) / "issues"
    reports = _read_jsonl(d / "reports.jsonl")
    links = {(r["n"], r["u"]): r["type"] for r in _read_jsonl(d / "links.jsonl")}
    return reports, links


def save_links(index_dir: str | Path, links: dict[tuple[int, str], str]) -> None:
    _write_jsonl(Path(index_dir) / "issues" / "links.jsonl",
                 [{"n": n, "u": h, "type": ty} for (n, h), ty in sorted(links.items())])
