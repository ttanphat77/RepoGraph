"""
Ca tự dựng cho bước 3: TF-IDF và Locus (mục 6.3), HIST theo phần lời (mục 6b), lớp history và chỉ mục hunk.
Giá trị mong đợi được tính tay từ công thức; phép tính ghi ở chú thích từng ca.

Chạy từ thư mục gốc repo:  .venv\\Scripts\\python.exe -m unittest tests.test_history -v
"""

import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.history import (
    LocusIndex, MsgIndex, build_history, build_hunks, code_terms, git_text, nl_terms, qvec, tfidf,
)

L2, L3, L15 = math.log(2), math.log(3), math.log(1.5)


class TextTest(unittest.TestCase):
    def test_nl_terms(self):
        # tách định danh, bỏ stop word của scikit-learn ("the", "is", cả "get") và từ khóa Python ("return"),
        # Porter ("running" → "run")
        self.assertEqual(nl_terms("The getUser_running is return"), ["user", "run"])

    def test_code_terms_a7(self):
        q = "Call `QuerySet.filter` and get_user(x) from Model.save and Count plainword"
        self.assertEqual(code_terms(q), ["QuerySet.filter", "QuerySet", "filter", "get_user",
                                         "Model.save", "Model", "save"])
        # A7 bỏ sót tên lớp chỉ viết hoa chữ đầu (Count), như đã ghi ở mục 6.4

    def test_tfidf_hand(self):
        # 3 tài liệu: d0 = {alpha: 1, beta: 2}, d1 = {alpha: 1, gamma: 1}, d2 = {delta: 1}
        X = sp.csr_matrix(np.array([[1, 2, 0, 0], [1, 0, 1, 0], [0, 0, 0, 1]], dtype=float))
        W, idf = tfidf(X)
        np.testing.assert_allclose(idf, [L15, L3, L3, L3])
        a, b = 1 * L15, (math.log(2) + 1) * L3            # w = (log f + 1)·idf
        n = math.hypot(a, b)
        np.testing.assert_allclose(W.toarray()[0], [a / n, b / n, 0, 0])
        np.testing.assert_allclose(W.toarray()[2], [0, 0, 0, 1])

    def test_qvec_hand(self):
        v = qvec(["alpha", "alpha", "beta", "zzz"], {"alpha": 0, "beta": 1}, np.array([L15, L3]))
        a, b = (math.log(2) + 1) * L15, L3                # từ không có trong vocab bị bỏ
        np.testing.assert_allclose(v, [a / math.hypot(a, b), b / math.hypot(a, b)])


def _unit(h, t, msg, touch):
    return {"h": h, "p": "p", "t": t, "merge": False, "msg": msg, "touch": touch, "touch_mod": []}


class LocusTest(unittest.TestCase):
    def setUp(self):
        units = [_unit("u0", 0, "init", []), _unit("u1", 100, "fix", ["m.py:f"]),
                 _unit("u2", 200, "omega", ["m.py:g"])]
        hunks = [{"u": "u1", "f": "m.py", "k": 0, "ids": ["m.py:f"], "text": "@@ -1 +1 @@\n-zeta\n+kappa_fn()"},
                 {"u": "u2", "f": "m.py", "k": 0, "ids": ["m.py:g"], "text": "@@ -1 +1 @@\n-iota\n+theta"}]
        fc = {"local:m.py:f", "local:m.py:g"}
        self.idx = LocusIndex(units, hunks, fc, {"kappa_fn", "f", "g"}, "local")

    def test_nl_ce_fix_hand(self):
        # d1 = zeta kappa fn fix, d2 = iota theta omega; mọi idf = log 2 → mỗi ô của d1 = 1/2.
        # q = "`kappa_fn`": NL token kappa, fn → cos = 2·(1/2)·(1/√2) = 1/√2.
        # CE: kappa_fn khớp tên, chỉ d1 có → cos = 1. α = min(1, 5·1/2) = 1.
        # Fix(f): u1 khớp "fix", t = (100 − 0)/(100 − 0) = 1 → 1/(1 + e^0) = 0,5 → β1·Fix = 0,05.
        r = self.idx.rank("`kappa_fn`", t_query=100)
        self.assertEqual(r["alpha"], 1.0)
        self.assertEqual([x["id"] for x in r["items"]], ["local:m.py:f"])
        self.assertAlmostEqual(r["items"][0]["score"], 1 / math.sqrt(2) + 1.0 + 0.05)

    def test_fix_only_function_still_ranked(self):
        # q = "theta": α = 0; d2 = iota theta omega → cos = 1/√3 cho g. f không khớp chữ nào nhưng có
        # Fix = 0,5 → điểm 0,05 (Fix kéo hàm từng được sửa lỗi lên, như Locus).
        r = self.idx.rank("theta", t_query=100)
        self.assertEqual(r["alpha"], 0.0)
        self.assertEqual([x["id"] for x in r["items"]], ["local:m.py:g", "local:m.py:f"])
        self.assertAlmostEqual(r["items"][0]["score"], 1 / math.sqrt(3))
        self.assertAlmostEqual(r["items"][1]["score"], 0.05)

    def test_function_not_in_graph_dropped(self):
        idx = LocusIndex([_unit("u2", 200, "omega", ["m.py:g"])],
                         [{"u": "u2", "f": "m.py", "k": 0, "ids": ["m.py:g"], "text": "@@ -1 +1 @@\n-iota\n+theta"}],
                         {"local:m.py:f"}, set(), "local")
        self.assertEqual(idx.rank("theta", t_query=300)["items"], [])


class MsgIndexTest(unittest.TestCase):
    def setUp(self):
        xs = [f"m.py:x{i}" for i in range(51)]
        self.units = [_unit("c1", 300, "kappa crash", ["m.py:f"]), _unit("c2", 200, "theta", ["m.py:g"]),
                      _unit("c3", 100, "kappa", ["m.py:h"]), _unit("c4", 50, "kappa big", xs),
                      _unit("c5", 40, "kappa outside", ["other.py:z"])]
        self.fc = {f"local:{k}" for k in ["m.py:f", "m.py:g", "m.py:h"] + xs}
        self.ast = ["local:m.py:g", "local:m.py:f"]

    def test_hand_example(self):
        # c4 sửa 51 hàm (> 50) và c5 sửa hàm ngoài graph → bị bỏ. Còn c1 = kappa crash, c2 = theta, c3 = kappa.
        # idf kappa = log 1,5; crash = theta = log 3. cos(c1) = log1,5/√(log²1,5 + log²3), cos(c3) = 1.
        # Danh sách lời: c3 (1), c1 (2). Danh sách nối AST: c2 (g hạng 1), c1 (f hạng 2).
        # s(c1) = 2/62, s(c2) = 1/61, s(c3) = 1/61; c2 và c3 hòa → c2 mới hơn đứng trước.
        r = MsgIndex(self.units, self.fc, "local").rank("kappa", self.ast)
        self.assertEqual([p["h"] for p in r["pool"]], ["c1", "c2", "c3"])
        self.assertAlmostEqual(r["pool"][0]["s"], 2 / 62)
        self.assertAlmostEqual(r["pool"][0]["cos"], L15 / math.hypot(L15, L3))
        self.assertEqual([(p["ast_r"], p["links"]) for p in r["pool"]], [(2, []), (1, []), (None, [])])
        self.assertEqual(r["pool"][0]["touch"], ["local:m.py:f"])
        self.assertEqual([(x["id"], round(x["score"], 6)) for x in r["items"]], [
            ("local:m.py:f", round(2 / 62, 6)), ("local:m.py:g", round(1 / 61, 6)),
            ("local:m.py:h", round(1 / 61, 6))])

    def test_linked_report_text_counts(self):
        # Không có liên kết: "crash" chỉ ở c1 → cos(c2) = 0. Có báo cáo #7 "crash failure" liên kết với c2:
        # crash ở c1 và c2 → idf = log 1,5 > 0 → cos(c2) > 0.
        plain = {p["h"]: p for p in MsgIndex(self.units, self.fc, "local").rank("crash", self.ast)["pool"]}
        self.assertEqual(plain["c2"]["cos"], 0.0)
        links = {"c2": [{"n": 7, "title": "crash failure", "body": "steps", "pr": False}]}
        pool = {p["h"]: p for p in MsgIndex(self.units, self.fc, "local", links).rank("crash", self.ast)["pool"]}
        self.assertGreater(pool["c2"]["cos"], 0.0)
        self.assertEqual(pool["c2"]["links"], [7])

    def test_empty(self):
        self.assertEqual(MsgIndex([], set(), "local").rank("x", []), {"items": [], "pool": []})


BASE = "def f():\n    x = 1\n    return x\n\n\nclass A:\n    def m1(self):\n        return 1\n\n\ndef g():\n    return 3\n"


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "core.autocrlf=false", *args], capture_output=True, check=True).stdout.decode()


class HistoryBuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = str(Path(self.tmp.name, "repo"))
        self.idx = str(Path(self.tmp.name, "index"))
        Path(self.repo).mkdir()
        _git(self.repo, "init", "-q")
        self._commit({"pkg/mod.py": BASE, "tests/test_mod.py": "def test_f():\n    pass\n"}, "base")
        self._commit({"pkg/mod.py": BASE.replace("x = 1", "x = 2")}, "Fix f bug")
        self._commit({"docs/a.rst": "Doc\n===\n", "tests/test_mod.py": "def test_f():\n    assert 1\n"}, "docs")
        self._commit({"pkg/mod.py": BASE.replace("x = 1", "x = 2").replace("return 1", "return 2")
                      .replace("return 3", "return 4")}, "change g and m1")

    def tearDown(self):
        self.tmp.cleanup()

    def _commit(self, files, msg):
        for rel, text in files.items():
            p = Path(self.repo, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode())
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", msg)

    def test_touch_sets_hunks_and_incremental(self):
        units, st = build_history(self.repo, self.idx)
        self.assertEqual([u["msg"] for u in units], ["change g and m1", "docs", "Fix f bug"])   # commit gốc bị bỏ
        self.assertEqual([u["touch"] for u in units],
                         [["pkg/mod.py:A:m1", "pkg/mod.py:g"], [], ["pkg/mod.py:f"]])  # tests/, docs/ ngoài graph
        self.assertEqual((st["commits"], st["new"], st["with_touch"]), (3, 3, 2))
        anc = set(git_text(self.repo, "rev-list", "HEAD").split())
        self.assertTrue(all(u["h"] in anc for u in units))

        hunks, hs = build_hunks(self.repo, self.idx, units)
        # sửa ở m1 và g cách nhau dưới 6 dòng → -U3 gộp thành một hunk, gán cho cả hai
        self.assertEqual(sorted(tuple(h["ids"]) for h in hunks),
                         [("pkg/mod.py:A:m1", "pkg/mod.py:g"), ("pkg/mod.py:f",)])
        self.assertEqual(hs["new_commits"], 2)

        self._commit({"pkg/mod.py": BASE.replace("x = 1", "x = 3").replace("return 1", "return 2")
                      .replace("return 3", "return 4")}, "again f")
        units2, st2 = build_history(self.repo, self.idx)
        self.assertEqual((st2["commits"], st2["new"], st2["reused"]), (4, 1, 3))
        self.assertEqual(units2[0]["touch"], ["pkg/mod.py:f"])
        hunks2, hs2 = build_hunks(self.repo, self.idx, units2)
        self.assertEqual((len(hunks2), hs2["new_commits"]), (3, 1))


if __name__ == "__main__":
    unittest.main()
