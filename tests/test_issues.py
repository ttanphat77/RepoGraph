"""
Ca tự dựng cho bước 4: liên kết báo cáo ↔ commit, SimiScore của BugLocator (mục 7 pipeline_design.md)
và việc tải issue từ GitHub (dừng khi hết lượt gọi, tải tiếp, tải phần cập nhật).

Chạy từ thư mục gốc repo:  .venv\\Scripts\\python.exe -m unittest tests.test_issues -v
"""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.issues import (
    IssueIndex, RateLimited, commit_texts, fetch_reports, github_slug, issue_links, pr_of, rate_limited,
)

SLUG = "pallets/flask"


def _rep(n, title, body="", pr=False):
    return {"n": n, "pr": pr, "title": title, "body": body, "created": 1_700_000_000 + n, "url": f"u{n}"}


def _unit(h, msg, touch):
    return {"h": h, "p": "p", "t": 0, "merge": False, "msg": msg, "touch": touch, "touch_mod": []}


class LinkTest(unittest.TestCase):
    def test_github_slug(self):
        self.assertEqual(github_slug("https://github.com/pallets/flask"), SLUG)
        self.assertEqual(github_slug("https://github.com/pallets/flask.git"), SLUG)
        self.assertEqual(github_slug("git@github.com:pallets/flask.git"), SLUG)
        self.assertIsNone(github_slug("https://gitlab.com/a/b"))
        self.assertIsNone(github_slug(None))

    def test_rate_limited(self):
        self.assertTrue(rate_limited(429, {}))
        self.assertTrue(rate_limited(403, {"X-RateLimit-Remaining": "0"}))      # giới hạn chính
        self.assertTrue(rate_limited(403, {"Retry-After": "60"}))               # giới hạn phụ
        self.assertFalse(rate_limited(403, {"X-RateLimit-Remaining": "57"}))    # thiếu quyền, không phải hết lượt
        self.assertFalse(rate_limited(403, {}))
        self.assertFalse(rate_limited(401, {}))

    def test_pr_of(self):
        self.assertEqual(pr_of("Merge pull request #100 from x/y\n\nbody"), 100)
        self.assertEqual(pr_of("Add thing (#101)\n\nmore"), 101)
        self.assertIsNone(pr_of("Add thing\n\n(#101)"))            # "(#N)" phải ở cuối dòng đầu
        self.assertIsNone(pr_of("Fix #5"))

    def test_links_from_message_and_pr_body(self):
        reports = [_rep(100, "PR merge", "This fixes #20 and refs #99", pr=True),
                   _rep(101, "PR squash", "Closes: #21", pr=True)]
        units = [
            _unit("a", "Merge pull request #100 from x/y", []),
            _unit("b", "Add thing (#101)", []),
            _unit("c", "Fixes #22, resolved pallets/flask#23 and close https://github.com/pallets/flask/issues/24", []),
            _unit("d", "fixed #25 but also other/repo#5 and https://github.com/other/repo/issues/6", []),
            _unit("e", "Mention #26 without keyword", []),
        ]
        self.assertEqual(sorted(issue_links(units, reports, SLUG)), [
            (20, "a"), (21, "b"), (22, "c"), (23, "c"), (24, "c"), (25, "d")])

    def test_commit_texts(self):
        reports = [_rep(7, "crash on x"), _rep(100, "PR", "fixes #7", pr=True), _rep(8, "other")]
        units = [_unit("a", "Merge pull request #100 from x/y", ["m.py:f"]), _unit("b", "plain", ["m.py:g"])]
        links = issue_links(units, reports, SLUG)
        out = commit_texts(units, reports, links)
        self.assertEqual([r["n"] for r in out["a"]], [7, 100])         # issue được đóng, rồi chính PR
        self.assertNotIn("b", out)


class SimiScoreTest(unittest.TestCase):
    def setUp(self):
        self.reports = [_rep(1, "kappa crash"), _rep(2, "theta"), _rep(3, "kappa"), _rep(4, "crash theta"),
                        _rep(5, "crash crash", pr=True)]                 # PR không là tài liệu
        self.units = [_unit("u1", "", ["m.py:f", "m.py:g"]), _unit("u2", "", ["m.py:g"]),
                      _unit("u3", "", ["m.py:g"]), _unit("u4", "", [])]
        self.links = {(1, "u1"): "fixed", (2, "u2"): "fixed", (4, "u3"): "fixed", (3, "u4"): "fixed"}

    def test_hand_example(self):
        # 4 tài liệu; kappa, crash, theta đều có df = 2 → idf như nhau → r1 = [kappa, crash] mỗi ô 1/√2,
        # r4 = [crash, theta] mỗi ô 1/√2. q = "crash" → sim(r1) = sim(r4) = 1/√2, sim(r2) = sim(r3) = 0.
        # Fix(r1) = {f, g} (|Fix| = 2), Fix(r4) = {g}, Fix(r3) = ∅ (u4 không sửa gì) → r3 không đóng góp.
        # SimiScore(f) = (1/√2)/2; SimiScore(g) = (1/√2)/2 + (1/√2)/1.
        idx = IssueIndex(self.reports, self.units, self.links, {"local:m.py:f", "local:m.py:g"}, "local")
        r = idx.rank("crash")
        s = 1 / math.sqrt(2)
        self.assertEqual([x["id"] for x in r["items"]], ["local:m.py:g", "local:m.py:f"])
        self.assertAlmostEqual(r["items"][0]["score"], s / 2 + s)
        self.assertAlmostEqual(r["items"][1]["score"], s / 2)
        self.assertEqual([(p["n"], round(p["cos"], 6), p["fix"], p["links"]) for p in r["pool"]], [
            (1, round(s, 6), ["local:m.py:f", "local:m.py:g"], ["fixed"]),
            (4, round(s, 6), ["local:m.py:g"], ["fixed"])])

    def test_report_without_fix_not_in_pool(self):
        r = IssueIndex(self.reports, self.units, self.links, {"local:m.py:f"}, "local").rank("kappa")
        self.assertEqual([p["n"] for p in r["pool"]], [1])               # r3 khớp hơn nhưng Fix(r3) rỗng
        self.assertEqual([x["id"] for x in r["items"]], ["local:m.py:f"])  # g không có trong graph

    def test_empty(self):
        self.assertEqual(IssueIndex([], [], {}, set(), "local").rank("x"), {"items": [], "pool": []})

    def test_reports_without_terms(self):
        # Báo cáo chỉ gồm stopword: không còn từ nào để tính TF-IDF, nên không xếp hạng thay vì báo lỗi
        reps = [_rep(1, "the", "and of")]
        idx = IssueIndex(reps, [_unit("u1", "", ["m.py:f"])], {(1, "u1"): "fixed"}, {"local:m.py:f"}, "local")
        self.assertEqual(idx.rank("crash"), {"items": [], "pool": []})


def _item(n, title, pr=False):
    it = {"number": n, "title": title, "body": None, "created_at": "2024-01-0%dT00:00:00Z" % (n % 9 + 1),
          "html_url": f"https://github.com/{SLUG}/issues/{n}"}
    if pr:
        it["pull_request"] = {}
    return it


class FakeGitHub:
    """Trả các trang theo URL; URL nằm trong `limited` gây RateLimited một lần."""

    def __init__(self, pages, limited=()):
        self.pages, self.limited, self.calls = pages, set(limited), []

    def __call__(self, url, token):
        self.calls.append(url)
        if url in self.limited:
            self.limited.discard(url)
            raise RateLimited(123.0)
        items, nxt = self.pages[url]
        return json.dumps(items), ({"Link": f'<{nxt}>; rel="next"'} if nxt else {})


class FetchTest(unittest.TestCase):
    def test_resume_after_rate_limit_then_incremental(self):
        base = (f"https://api.github.com/repos/{SLUG}/issues?state=closed&per_page=100"
                "&sort=created&direction=asc")
        gh = FakeGitHub({base: ([_item(1, "a"), _item(2, "b", pr=True)], "P2"),
                         "P2": ([_item(3, "c")], None)}, limited={"P2"})
        with tempfile.TemporaryDirectory() as d:
            r1 = fetch_reports(SLUG, d, token="", http=gh)
            self.assertEqual((r1["complete"], r1["pages"], r1["reset"]), (False, 1, 123.0))
            self.assertFalse(Path(d, "issues", "reports.jsonl").exists())

            r2 = fetch_reports(SLUG, d, token="", http=gh)                 # đi tiếp từ link P2
            self.assertEqual((r2["complete"], r2["reports"]), (True, 3))
            self.assertEqual(gh.calls, [base, "P2", "P2"])
            rows = [json.loads(l) for l in Path(d, "issues", "reports.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([(r["n"], r["pr"]) for r in rows], [(1, False), (2, True), (3, False)])
            since = json.loads(Path(d, "issues", "fetch_state.json").read_text(encoding="utf-8"))["fetched_at"]

            upd = f"{base}&since={since}"
            gh.pages[upd] = ([_item(2, "b edited", pr=True), _item(4, "d")], None)
            r3 = fetch_reports(SLUG, d, token="", http=gh)                 # chỉ tải phần cập nhật
            self.assertEqual(gh.calls[-1], upd)
            self.assertEqual((r3["complete"], r3["reports"], r3["new_rows"]), (True, 4, 2))
            rows = {json.loads(l)["n"]: json.loads(l)
                    for l in Path(d, "issues", "reports.jsonl").read_text(encoding="utf-8").splitlines()}
            self.assertEqual(rows[2]["title"], "b edited")
            self.assertFalse(Path(d, "issues", "reports.jsonl.part").exists())


if __name__ == "__main__":
    unittest.main()
