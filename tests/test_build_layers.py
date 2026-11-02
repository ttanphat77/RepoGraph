"""
Ca tự dựng cho bước 1: bộ lọc file, lớp doc (mục 2.2 pipeline_design.md) và cache embedding.

Chạy từ thư mục gốc repo:  .venv\\Scripts\\python.exe -m unittest tests.test_build_layers -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import embeddings
from pipeline.doc_extractor import (
    MAX_CHUNK_CHARS, DocExtractor, build_name_index, get_doc_files,
    resolve_doc_links, split_chunks,
)
from pipeline.repo_manager import filter_source_files


def _code(label, nid, name, file):
    return {"labels": [label], "id": nid, "properties": {"name": name, "file": file}}


def _links(text, path="docs/api.rst"):
    return DocExtractor(path, ".").extract_text(text)


class FileFilterTest(unittest.TestCase):
    def test_skip_dirs_and_config_files(self):
        paths = [
            "src/flask/app.py",
            "tests/test_app.py",
            "src/pkg/tests/helpers.py",
            "examples/tutorial/flaskr/db.py",
            "docs/conf.py",
            "benchmarks/bench.py",
            "setup.py",
            "src/pkg/conftest.py",
            "src/pkg/testing.py",       # tên file chứa "test" nhưng không phải thư mục test → giữ
        ]
        self.assertEqual(filter_source_files(paths), ["src/flask/app.py", "src/pkg/testing.py"])


class ChunkTest(unittest.TestCase):
    def test_split_by_heading(self):
        text = "Title\n=====\n\nIntro text.\n\nSection A\n---------\n\nBody A.\n\nEmpty\n-----\n\nSection B\n---------\nBody B."
        self.assertEqual(split_chunks(text),
                         [("Title", "Intro text."), ("Section A", "Body A."), ("Section B", "Body B.")])

    def test_short_underline_is_not_heading(self):
        # gạch chân ngắn hơn tiêu đề → không phải heading → cả file là một chunk
        self.assertEqual(split_chunks("Long title here\n---\nbody"), [("", "Long title here\n---\nbody")])

    def test_no_heading(self):
        self.assertEqual(split_chunks("just text\nmore"), [("", "just text\nmore")])
        self.assertEqual(split_chunks("   \n"), [])

    def test_long_body_split_by_paragraph_keeps_heading(self):
        para = "x" * 700
        body = "\n\n".join([para] * 4)          # 4 đoạn 700 ký tự → 2 phần, mỗi phần 2 đoạn
        chunks = split_chunks(f"Big\n===\n\n{body}")
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(h == "Big" for h, _ in chunks))
        self.assertTrue(all(len(b) <= MAX_CHUNK_CHARS for _, b in chunks))
        self.assertEqual("\n\n".join(b for _, b in chunks), body)


class DocLinkTest(unittest.TestCase):
    def setUp(self):
        self.nodes = [
            _code("Class", "local:src/flask/app.py:Flask", "Flask", "src/flask/app.py"),
            _code("Function", "local:src/flask/app.py:Flask:run", "run", "src/flask/app.py"),
            _code("Function", "local:src/flask/helpers.py:url_for", "url_for", "src/flask/helpers.py"),
            _code("Function", "local:src/pkg/a.py:get", "get", "src/pkg/a.py"),
            _code("Function", "local:src/pkg/b.py:get", "get", "src/pkg/b.py"),
            _code("Class", "local:tests/test_app.py:Flask", "Flask", "tests/test_app.py"),
            _code("Module", "local:src/flask/app.py", "app.py", "src/flask/app.py"),
        ]
        self.index = build_name_index(self.nodes)

    def _edges(self, text, extra_docs=()):
        results = [_links(text)] + [_links("x", p) for p in extra_docs]
        return resolve_doc_links(results, self.index)

    def _targets(self, text):
        return sorted(e["target"] for e in self._edges(text) if e["type"] == "Documents")

    def test_index_skips_test_files_and_modules(self):
        self.assertEqual(self.index["Flask"], {"local:src/flask/app.py:Flask"})
        self.assertEqual(self.index["flask.Flask"], {"local:src/flask/app.py:Flask"})   # src. bị bỏ
        self.assertEqual(self.index["Flask.run"], {"local:src/flask/app.py:Flask:run"})
        self.assertNotIn("app.py", self.index)

    def test_directive_with_module_context(self):
        text = ("API\n===\n\n.. currentmodule:: flask\n\n.. autoclass:: Flask\n\n"
                ".. method:: run(host=None)\n")
        self.assertEqual(self._targets(text),
                         ["local:src/flask/app.py:Flask", "local:src/flask/app.py:Flask:run"])

    def test_roles_and_titled_role(self):
        text = "Use\n===\n\nSee :func:`url_for` and :meth:`run <flask.Flask.run>` and :class:`~flask.Flask`."
        self.assertEqual(self._targets(text), [
            "local:src/flask/app.py:Flask", "local:src/flask/app.py:Flask:run",
            "local:src/flask/helpers.py:url_for"])

    def test_ambiguous_name_not_linked(self):
        self.assertEqual(self._targets("X\n=\n\n:func:`get`"), [])

    def test_ambiguous_name_narrowed_by_module_context(self):
        self.assertEqual(self._targets("X\n=\n\n.. currentmodule:: pkg.a\n\n:func:`get`"),
                         ["local:src/pkg/a.py:get"])

    def test_module_none_resets_context(self):
        text = "X\n=\n\n.. currentmodule:: pkg.a\n\n.. currentmodule:: None\n\n:func:`get`"
        self.assertEqual(self._targets(text), [])

    def test_unknown_name_not_linked(self):
        self.assertEqual(self._targets("X\n=\n\n:func:`does_not_exist`"), [])

    def test_doc_reference(self):
        edges = self._edges("X\n=\n\nSee :doc:`quickstart` and :doc:`Guide </missing>`.",
                            extra_docs=["docs/quickstart.rst"])
        refs = [(e["source"], e["target"]) for e in edges if e["type"] == "References"]
        self.assertEqual(refs, [("chunk:docs/api.rst:0", "doc:docs/quickstart.rst")])

    def test_nodes_and_haschunk(self):
        r = _links("A\n=\n\nOne.\n\nB\n=\n\nTwo.")
        self.assertEqual([n["id"] for n in r["nodes"]],
                         ["doc:docs/api.rst", "chunk:docs/api.rst:0", "chunk:docs/api.rst:1"])
        self.assertEqual(r["nodes"][0]["properties"]["title"], "A")
        self.assertEqual([e["target"] for e in r["edges"]], ["chunk:docs/api.rst:0", "chunk:docs/api.rst:1"])

    def test_get_doc_files(self):
        with tempfile.TemporaryDirectory() as d:
            for p in ("docs/index.rst", "docs/guide.md", "docs/_build/out.rst",
                      "docs/requirements.txt", "docs/api/ref.txt", "README.md"):
                Path(d, p).parent.mkdir(parents=True, exist_ok=True)
                Path(d, p).write_text("x", encoding="utf-8")
            self.assertEqual(get_doc_files(d), ["docs/index.rst", "docs/guide.md", "docs/api/ref.txt"])


class _FakeModel:
    """Model giả: vector 3 chiều tính từ độ dài văn bản, đếm số văn bản đã encode."""

    def __init__(self):
        self.seen = []

    def encode(self, texts, **_):
        self.seen += texts
        v = np.array([[len(t), 1.0, 0.0] for t in texts], dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


class EmbeddingTest(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeModel()
        self._orig = embeddings._MODEL
        embeddings._MODEL = (self.fake, "cpu", "float32")

    def tearDown(self):
        embeddings._MODEL = self._orig

    def test_embed_text(self):
        fn = {"labels": ["Function"], "id": "f", "properties": {"name": "f", "source": "y" * 3000}}
        empty = {"labels": ["Class"], "id": "c", "properties": {"name": "C", "source": ""}}
        chunk = {"labels": ["DocChunk"], "id": "d", "properties": {"heading": "H", "text": "T"}}
        self.assertEqual(len(embeddings.embed_text(fn)), 2000)
        self.assertEqual(embeddings.embed_text(empty), "Class C")
        self.assertEqual(embeddings.embed_text(chunk), "H\nT")

    def test_cache_reuses_vectors_across_builds(self):
        nodes = [
            {"labels": ["Function"], "id": "a", "properties": {"name": "a", "source": "def a(): pass"}},
            {"labels": ["Function"], "id": "b", "properties": {"name": "b", "source": "def a(): pass"}},
            {"labels": ["Module"], "id": "m", "properties": {"name": "m"}},
        ]
        with tempfile.TemporaryDirectory() as d:
            s1 = embeddings.embed_nodes(nodes, d)
            self.assertEqual((s1["n"], s1["encoded"], s1["reused"]), (2, 1, 1))   # hai node cùng văn bản
            nodes[1]["properties"]["source"] = "def b(): return 1"
            s2 = embeddings.embed_nodes(nodes, d)                                # lần build sau, cache trên đĩa
            self.assertEqual((s2["encoded"], s2["reused"]), (1, 1))
            self.assertEqual(self.fake.seen, ["def a(): pass", "def b(): return 1"])
            ids = __import__("json").loads(Path(d, "node_ids.json").read_text(encoding="utf-8"))
            vecs = np.load(Path(d, "node_vectors.npy"))
            self.assertEqual(ids, ["a", "b"])
            self.assertEqual(vecs.shape, (2, 3))
            self.assertAlmostEqual(float(np.linalg.norm(vecs[0])), 1.0, places=5)
            self.assertEqual(s2["encoders"], ["cpu/float32"])
            self.assertFalse(any(p.endswith(".tmp") for p in os.listdir(d)))


if __name__ == "__main__":
    unittest.main()
