"""
Ca tự dựng cho bước 2: xếp hạng AST, trộn RRF, xếp file, phần Thực thể, caller/callee.
Kết quả mong đợi được tính tay từ công thức ở mục 4 và mục 8 pipeline_design.md.

Chạy từ thư mục gốc repo:  .venv\\Scripts\\python.exe -m unittest tests.test_ranking -v
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.ranking import RepoIndex, embed_query_text, file_rank, rrf_fuse, tokenize_code


def _n(nid, label, name, file, source=""):
    return {"id": nid, "label": label, "name": name, "file": file,
            "start_line": 1, "end_line": 2, "source": source}


class TextTest(unittest.TestCase):
    def test_tokenize_code(self):
        self.assertEqual(tokenize_code("getUserName_v2(x) QuerySet"),
                         ["get", "user", "name", "v2", "x", "query", "set"])

    def test_embed_query_text(self):
        q = "Bug here\n```python\nprint(1)\n```\nmore"
        self.assertEqual(embed_query_text(q), "Bug here\n \nmore")
        self.assertEqual(len(embed_query_text("a" * 5000)), 2000)


class RrfFuseTest(unittest.TestCase):
    def test_hand_example(self):
        # a = 1/61, b = 1/62, c = 1/63 + 1/61, d = 1/62. b và d hòa → b (có hạng AST) trước d.
        out = rrf_fuse(["a", "b", "c"], {"HIST": ["c", "d"]})
        self.assertEqual([x["id"] for x in out], ["c", "a", "b", "d"])
        self.assertAlmostEqual(out[0]["score"], 1 / 63 + 1 / 61)
        self.assertAlmostEqual(out[1]["score"], 1 / 61)
        self.assertEqual(out[0]["ranks"], {"AST": 3, "HIST": 1})
        self.assertEqual(out[3]["ranks"], {"AST": None, "HIST": 2})

    def test_tie_outside_ast_by_id(self):
        out = rrf_fuse(["a"], {"S1": ["z"], "S2": ["y"]})
        self.assertEqual([x["id"] for x in out], ["a", "y", "z"])

    def test_limit(self):
        self.assertEqual(len(rrf_fuse(["a", "b", "c"], {}, limit=2)), 2)


class FileRankTest(unittest.TestCase):
    def test_first_appearance(self):
        items = [{"id": "x:f1.py:a", "score": 0.3}, {"id": "x:f2.py:b", "score": 0.2},
                 {"id": "x:f1.py:c", "score": 0.1}]
        out = file_rank(items, lambda i: i.split(":")[1])
        self.assertEqual([(f["file"], f["best_pos"], f["score"]) for f in out],
                         [("f1.py", 1, 0.3), ("f2.py", 2, 0.2)])


def _toy_index(vec_ids=None):
    """
    3 hàm + 1 module. Query "alpha": chỉ alpha chứa token alpha → BM25 (hạng từ 0):
    alpha 0, rồi các node điểm 0 theo id: module 1, delta 2, gamma 3.
    Vector query [0, 1]: cos delta 1.0, gamma 0.8, alpha 0.0 → hạng delta 0, gamma 1, alpha 2.
    """
    nodes = [
        _n("x:pkg/m.py", "Module", "pkg/m.py", "pkg/m.py"),
        _n("x:pkg/m.py:alpha", "Function", "alpha", "pkg/m.py", "def alpha(): pass"),
        _n("x:pkg/m.py:gamma", "Function", "gamma", "pkg/m.py", "def gamma(): pass"),
        _n("x:pkg/m.py:delta", "Function", "delta", "pkg/m.py", "def delta(): pass"),
    ]
    ids = vec_ids or ["x:pkg/m.py:alpha", "x:pkg/m.py:delta", "x:pkg/m.py:gamma"]
    table = {"x:pkg/m.py:alpha": [1.0, 0.0], "x:pkg/m.py:delta": [0.0, 1.0], "x:pkg/m.py:gamma": [0.6, 0.8]}
    vecs = np.array([table[i] for i in ids], dtype=np.float32)
    return RepoIndex(nodes, [], ids, vecs, encode_query=lambda t: np.array([0.0, 1.0], dtype=np.float32))


class AstRankTest(unittest.TestCase):
    def test_hand_example(self):
        # alpha = 1/60 + 1/62, delta = 1/62 + 1/60 (hòa → id), gamma = 1/63 + 1/61, module = 1/61 (bị lọc)
        out = _toy_index().ast_rank("alpha")
        self.assertEqual([x["id"] for x in out], ["x:pkg/m.py:alpha", "x:pkg/m.py:delta", "x:pkg/m.py:gamma"])
        self.assertAlmostEqual(out[0]["score"], 1 / 60 + 1 / 62)
        self.assertAlmostEqual(out[2]["score"], 1 / 63 + 1 / 61)
        self.assertEqual((out[0]["bm25_rank"], out[0]["vec_rank"]), (1, 3))
        self.assertEqual((out[1]["bm25_rank"], out[1]["vec_rank"]), (3, 1))
        self.assertAlmostEqual(out[2]["cos"], 0.8, places=6)
        self.assertGreater(out[0]["bm25_score"], 0.0)
        self.assertEqual(out[1]["bm25_score"], 0.0)

    def test_truncate_before_filter(self):
        # depth 2: BM25 giữ alpha, module; vector giữ delta, gamma. Điểm: alpha = delta = 1/60,
        # module = gamma = 1/61. Giữ 2 node đầu (alpha, delta) rồi mới lọc Function/Class.
        out = _toy_index().ast_rank("alpha", depth=2)
        self.assertEqual([x["id"] for x in out], ["x:pkg/m.py:alpha", "x:pkg/m.py:delta"])
        self.assertIsNone(out[0]["vec_rank"])

    def test_deterministic_across_indexes(self):
        a = _toy_index().ast_rank("alpha gamma")
        b = _toy_index(vec_ids=["x:pkg/m.py:gamma", "x:pkg/m.py:alpha", "x:pkg/m.py:delta"]).ast_rank("alpha gamma")
        self.assertEqual(a, b)

    def test_missing_vector_warning(self):
        idx = _toy_index(vec_ids=["x:pkg/m.py:alpha", "x:pkg/m.py:delta"])
        self.assertEqual(len(idx.warnings), 1)
        self.assertNotIn("x:pkg/m.py:gamma", [x["id"] for x in idx.ast_rank("alpha") if x["vec_rank"]])


class EntityAndNeighborTest(unittest.TestCase):
    def setUp(self):
        nodes = [
            _n("l:src/flask/app.py", "Module", "src/flask/app.py", "src/flask/app.py"),
            _n("l:src/flask/app.py:Flask", "Class", "Flask", "src/flask/app.py", "class Flask: ..."),
            _n("l:src/flask/app.py:Flask:run", "Function", "run", "src/flask/app.py", "def run(): ..."),
            _n("l:src/flask/cli.py:run_command", "Function", "run_command", "src/flask/cli.py", "def run_command(): ..."),
            _n("l:src/flask/cli.py:get_debug", "Function", "get_debug", "src/flask/cli.py", "def get_debug(): ..."),
            _n("l:src/flask/helpers.py:get_debug", "Function", "get_debug", "src/flask/helpers.py", "def get_debug(): ..."),
        ]
        calls = [("l:src/flask/cli.py:run_command", "l:src/flask/app.py:Flask:run"),
                 ("l:src/flask/cli.py:get_debug", "l:src/flask/app.py:Flask:run"),
                 ("l:src/flask/app.py:Flask:run", "l:src/flask/helpers.py:get_debug"),
                 ("l:src/flask/app.py:Flask:run", "l:outside:x")]          # đích ngoài graph → bỏ
        fc = [n["id"] for n in nodes if n["label"] != "Module"]
        self.idx = RepoIndex(nodes, calls, fc, np.eye(len(fc), dtype=np.float32),
                             encode_query=lambda t: np.zeros(len(fc), dtype=np.float32))

    def test_entities(self):
        out = self.idx.find_entities("Calling `get_debug` on Flask from src/flask/app.py fails")
        self.assertEqual(out["candidates"], ["Calling", "Flask", "app", "get_debug", "src/flask/app.py"])
        self.assertEqual([(x["id"], x["match"], x["matched"]) for x in out["items"]], [
            ("l:src/flask/cli.py:get_debug", "name", "get_debug"),
            ("l:src/flask/helpers.py:get_debug", "name", "get_debug"),
            ("l:src/flask/app.py:Flask", "name", "Flask"),
            ("l:src/flask/app.py", "file", "app"),
        ])
        self.assertEqual(out["total"], 4)
        self.assertEqual(len(self.idx.find_entities("get_debug", limit=1)["items"]), 1)

    def test_no_entities(self):
        self.assertEqual(self.idx.find_entities("nothing named here")["items"], [])

    def test_neighbors_sorted_by_ast_rank_then_id(self):
        pos = {"l:src/flask/cli.py:get_debug": 1, "l:src/flask/cli.py:run_command": 7}
        nb = self.idx.neighbors("l:src/flask/app.py:Flask:run", pos)
        self.assertEqual([x["id"] for x in nb["callers"]],
                         ["l:src/flask/cli.py:get_debug", "l:src/flask/cli.py:run_command"])
        self.assertEqual([x["id"] for x in nb["callees"]], ["l:src/flask/helpers.py:get_debug"])
        self.assertEqual((nb["n_callers"], nb["n_callees"]), (2, 1))
        self.assertIsNone(nb["callees"][0]["ast_rank"])
        nb1 = self.idx.neighbors("l:src/flask/app.py:Flask:run", {}, limit=1)
        self.assertEqual([x["id"] for x in nb1["callers"]], ["l:src/flask/cli.py:get_debug"])
        self.assertNotIn("source", nb1["callers"][0])


if __name__ == "__main__":
    unittest.main()
