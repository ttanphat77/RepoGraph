"""
Ca tự dựng cho bước 6: pool DOC, định dạng phần tử v5, trích dẫn, và bản ghi lần chạy
(đủ 8 khối, kể cả khi truy hồi hoặc LLM lỗi). Không gọi mạng: LLM và bộ đếm token là hàm giả.

Chạy từ thư mục gốc repo:  .venv\\Scripts\\python.exe -m unittest tests.test_answer -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.context import format_doc, format_hist, format_issue, format_sections, qualified, retrieve_kp
from pipeline.evaluator import Engine, run_prompt
from pipeline.ranking import RepoIndex
from pipeline.run_record import parse_citations

BLOCKS = ["run", "index", "config", "retrieval", "llm", "citations", "timing", "warnings"]


def _toy_index(doc_edges=True):
    nodes = [
        {"id": "local:m.py", "label": "Module", "name": "m.py", "file": "m.py",
         "start_line": None, "end_line": None, "source": None},
        {"id": "local:m.py:alpha", "label": "Function", "name": "alpha", "file": "m.py",
         "start_line": 1, "end_line": 3, "source": "def alpha():\n    return beta()\n"},
        {"id": "local:m.py:beta", "label": "Function", "name": "beta", "file": "m.py",
         "start_line": 5, "end_line": 6, "source": "def beta():\n    return 1\n"},
    ]
    chunks = [{"id": "chunk:docs/a.rst:0", "file": "docs/a.rst", "heading": "Usage", "text": "Call alpha to start."},
              {"id": "chunk:docs/a.rst:1", "file": "docs/a.rst", "heading": "Other", "text": "Unrelated words here."}]
    ids = ["local:m.py:alpha", "local:m.py:beta", "chunk:docs/a.rst:0", "chunk:docs/a.rst:1"]
    vecs = np.array([[1, 0], [0, 1], [1, 0], [0, 1]], dtype=np.float32)
    state = {"id_prefix": "local", "head_sha": "abcdef1234567890", "remote": "https://github.com/x/y",
             "built_at": "2026-11-02T00:00:00+00:00"}
    return RepoIndex(nodes, [("local:m.py:alpha", "local:m.py:beta")], ids, vecs, state,
                     encode_query=lambda t: np.array([1.0, 0.0], dtype=np.float32), chunks=chunks,
                     doc_edges=[("chunk:docs/a.rst:0", "local:m.py:alpha")] if doc_edges else [])


def _engine(index_dir, ri=None):
    return Engine(index_dir, ri or _toy_index(), None, None, None, [], [], 0.0)


class DocPoolTest(unittest.TestCase):
    def test_only_chunks_with_documents_edges(self):
        r = _toy_index().doc_pool("alpha")
        self.assertEqual(r["pool"], "doc_cand")
        self.assertEqual([(x["id"], x["targets"]) for x in r["items"]],
                         [("chunk:docs/a.rst:0", ["local:m.py:alpha"])])
        self.assertAlmostEqual(r["items"][0]["score"], 2 / 60)          # một chunk: hạng 0 ở cả hai danh sách

    def test_fallback_to_all_chunks(self):
        # Không có cạnh Documents → mọi chunk. "alpha" chỉ ở chunk 0 (BM25 hạng 0), cos chunk 0 = 1, chunk 1 = 0.
        r = _toy_index(doc_edges=False).doc_pool("alpha")
        self.assertEqual(r["pool"], "doc_cand_all")
        self.assertEqual([x["id"] for x in r["items"]], ["chunk:docs/a.rst:0", "chunk:docs/a.rst:1"])
        self.assertAlmostEqual(r["items"][0]["score"], 2 / 60)
        self.assertAlmostEqual(r["items"][1]["score"], 2 / 61)


class FormatTest(unittest.TestCase):
    def test_qualified(self):
        self.assertEqual(qualified("local:src/flask/app.py:Flask:url_for"), "Flask.url_for")
        self.assertEqual(qualified("local:src/flask/app.py"), "src/flask/app.py")

    def test_v5_formats(self):
        self.assertEqual(format_doc({"tag": "D1", "file": "docs/a.rst", "heading": "Usage", "text": "Body"}),
                         "[D1] Documentation passage\nFile: docs/a.rst\nSection: Usage\nText:\nBody")
        h = {"tag": "H2", "h": "0123456789abcdef", "t": 1700000000, "msg": "Fix crash\n\nlong",
             "linked": [{"n": 9, "title": "PR nine", "body": "pr body"}, {"n": 3, "title": "Crash", "body": "trace"}]}
        self.assertEqual(format_hist(h), "[H2] Past commit 01234567, committed 2023-11-14\nCommit message:\n"
                         "Fix crash\n\nlong\nLinked ticket or pull request #3: Crash\ntrace\n"
                         "Linked ticket or pull request #9: PR nine\npr body")
        self.assertEqual(format_issue({"tag": "I1", "n": 7, "created": 1700000000, "title": "Bug", "body": "B"}),
                         "[I1] Past bug report #7, created 2023-11-14: Bug\nB")


class CitationTest(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            timing = {}
            self.kp = retrieve_kp(_engine(d), "Why does `alpha` call beta?", 1.0, timing)

    def test_valid_and_invalid(self):
        answer = ("See `alpha` in `m.py:2` [C1] and [C2, D1]. Also `beta` in `m.py:40` and `x` in `z.py:1`. "
                  "Docs [D7] and [H1]. Entity [E1].")
        c = parse_citations(answer, self.kp)
        self.assertEqual(c["cited_items"], ["C1", "C2", "D1", "D7", "H1", "E1"])
        self.assertEqual(c["invalid_items"], ["D7", "H1"])              # D7 ngoài pool, không có commit nào
        self.assertEqual([(s["path"], s["line"], s["valid"]) for s in c["cited_symbols"]],
                         [("m.py", 2, True), ("m.py", 40, False), ("z.py", 1, False)])
        self.assertEqual(len(c["invalid_symbols"]), 2)
        self.assertEqual(c["cited_per_section"]["code"], 2)
        self.assertEqual(c["cited_per_section"]["doc"], 1)

    def test_kp_sections(self):
        self.assertEqual([c["tag"] for c in self.kp["code"]], ["C1", "C2"])
        self.assertEqual(self.kp["code"][0]["linked_doc"], ["D1"])        # chunk có cạnh Documents tới alpha
        self.assertEqual(self.kp["doc"][0]["linked_code"], ["C1"])
        self.assertEqual([e["id"] for e in self.kp["entities"]["items"]], ["local:m.py:alpha"])
        s = format_sections(self.kp)
        self.assertEqual(s["hist"], "(none)")
        self.assertIn("Called by: none found in the call graph", s["code"])
        self.assertIn("Calls: `beta` (m.py:5)", s["code"])


def _fake_counter(parts):
    return {k: len(v) // 4 for k, v in parts.items()}


class RunRecordTest(unittest.TestCase):
    def _tmp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return d.name

    def _run(self, llm, engine=None, **kw):
        d = self._tmp()
        rec, run_dir = run_prompt("Why does `alpha` call beta?", index_dir=d, engine=engine or _engine(d),
                                  llm=llm, counter=_fake_counter, t_query=1.0, **kw)
        return d, rec, run_dir

    def test_success_record(self):
        seen = {}

        def llm(system, user, on_text):
            seen["user"] = user
            return {"answer": "It calls `beta` in `m.py:5` [C2].", "finish_reason": "STOP",
                    "prompt_token_count": 1000, "candidates_token_count": 20, "thoughts_token_count": 5,
                    "total_token_count": 1025, "error": None}
        d, rec, run_dir = self._run(llm)
        self.assertEqual(list(rec), BLOCKS)
        self.assertEqual(rec["llm"]["section_tokens_gap"],
                         round((1000 - rec["llm"]["section_tokens_sum"]) / 1000, 4))
        self.assertEqual(rec["citations"]["cited_items"], ["C2"])
        self.assertTrue(rec["retrieval"]["code"][1]["cited"])
        self.assertNotIn("source", rec["retrieval"]["code"][0])          # toàn văn nằm ở prompt.txt
        self.assertIn("[C1] Function `alpha`", seen["user"])
        for f in ("record.json", "prompt.txt", "answer.md"):
            self.assertTrue((run_dir / f).exists())
        line = json.loads((Path(d) / "runs" / "index.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((line["items"]["code"], line["tokens"]["in"], line["invalid"]), (2, 1000, 0))

    def test_llm_error_still_records(self):
        def llm(system, user, on_text):
            return {"answer": "", "finish_reason": "ERROR", "error": "ClientError: 401", "prompt_token_count": None}
        _, rec, run_dir = self._run(llm)
        self.assertEqual(list(rec), BLOCKS)
        self.assertEqual(rec["llm"]["finish_reason"], "ERROR")
        self.assertTrue(any("LLM call failed" in w for w in rec["warnings"]))
        self.assertIsNotNone(rec["retrieval"])
        self.assertTrue((run_dir / "record.json").exists())

    def test_config_records_model_used(self):
        def llm(system, user, on_text):
            return {"answer": "", "finish_reason": "STOP", "prompt_token_count": 10, "error": None}
        _, rec_a, _ = self._run(llm, model="model-a")
        _, rec_b, _ = self._run(llm, model="model-b")
        self.assertEqual((rec_a["config"]["llm_model"], rec_b["config"]["llm_model"]), ("model-a", "model-b"))
        self.assertNotEqual(rec_a["config"]["config_sha"], rec_b["config"]["config_sha"])

    def test_retrieval_error_still_records(self):
        ri = _toy_index()
        ri.ast_rank = lambda q, depth=500: (_ for _ in ()).throw(RuntimeError("boom"))
        called = []
        d = self._tmp()
        rec, run_dir = run_prompt("x", index_dir=d, engine=_engine(d, ri), llm=lambda *a: called.append(1),
                                  counter=_fake_counter, t_query=1.0)
        self.assertEqual(list(rec), BLOCKS)
        self.assertEqual(called, [])                                     # không gọi LLM
        self.assertEqual(rec["llm"]["finish_reason"], "NOT_RUN")
        self.assertTrue(any("retrieval failed: RuntimeError: boom" in w for w in rec["warnings"]))
        self.assertTrue((run_dir / "record.json").exists())


if __name__ == "__main__":
    unittest.main()
