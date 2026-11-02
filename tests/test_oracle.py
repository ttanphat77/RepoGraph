"""
Ca tự dựng cho oracle (mục 3 pipeline_design.md, việc 1.1). Mỗi ca tạo một commit trong repo git tạm,
lấy diff -U0 thật giữa hai commit, rồi so tập hàm/lớp mà oracle trả với kết quả mong đợi.

Chạy từ thư mục gốc repo:  .venv\\Scripts\\python.exe -m unittest tests.test_oracle -v
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.oracle import file_nodes_at, get_oracle

BASE = '''import os

X = 1


class A:
    attr = 1

    def m1(self):
        a = 1
        return a

    @property
    def p(self):
        return 2


def f():
    x = 1
    return x


def g():
    return 3
'''


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "core.autocrlf=false", *args],
                          capture_output=True, check=True).stdout.decode("utf-8")


class OracleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        _git(self.repo, "init", "-q")
        self._write("pkg/mod.py", BASE)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base")
        self.base = _git(self.repo, "rev-parse", "HEAD").strip()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rel, text):
        p = Path(self.repo, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))

    def _oracle(self, new_text=None, rel="pkg/mod.py", extra=None, rename_to=None):
        if rename_to:
            _git(self.repo, "mv", rel, rename_to)
            rel_new = rename_to
        else:
            rel_new = rel
        if new_text is not None:
            self._write(rel_new, new_text)
        for p, t in (extra or {}).items():
            self._write(p, t)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "change")
        diff = _git(self.repo, "diff", "-U0", "-M", self.base, "HEAD", "--", "*.py")
        nodes = file_nodes_at(self.repo, self.base, rel)
        return get_oracle(diff, nodes)

    def _ids(self, new_text, **kw):
        return sorted(self._oracle(new_text, **kw)["nodes"])

    # ── dòng xóa / sửa ───────────────────────────────────────────────────────
    def test_edit_inside_method_gives_method_not_class(self):
        self.assertEqual(self._ids(BASE.replace("a = 1", "a = 2")), ["pkg/mod.py:A:m1"])

    def test_class_level_line_gives_class(self):
        self.assertEqual(self._ids(BASE.replace("attr = 1", "attr = 2")), ["pkg/mod.py:A"])

    def test_module_level_change_gives_module(self):
        r = self._oracle(BASE.replace("X = 1", "X = 2"))
        self.assertEqual(sorted(r["nodes"]), ["pkg/mod.py"])
        self.assertEqual(r["module_only"], {"pkg/mod.py"})

    def test_remove_line(self):
        self.assertEqual(self._ids(BASE.replace("def g():\n    return 3\n", "def g():\n    pass\n")),
                         ["pkg/mod.py:g"])

    def test_changed_existing_decorator(self):
        self.assertEqual(self._ids(BASE.replace("@property", "@cached_property")), ["pkg/mod.py:A:p"])

    # ── khối dòng thêm ───────────────────────────────────────────────────────
    def test_insert_in_middle_of_body(self):
        self.assertEqual(self._ids(BASE.replace("    x = 1\n", "    x = 1\n    y = x\n")), ["pkg/mod.py:f"])

    def test_append_to_end_of_body_deeper_indent(self):
        self.assertEqual(self._ids(BASE.replace("    return x\n", "    return x\n    print(x)\n")),
                         ["pkg/mod.py:f"])

    def test_new_function_after_body_is_new_code(self):
        # dòng def h() thụt bằng dòng def f() → bắt đầu code mới, không gán cho f → chỉ đổi cấp module
        new = BASE.replace("    return x\n", "    return x\n\n\ndef h():\n    return 5\n")
        r = self._oracle(new)
        self.assertEqual(sorted(r["nodes"]), ["pkg/mod.py"])

    def test_new_decorator_above_def(self):
        self.assertEqual(self._ids(BASE.replace("def g():", "@staticmethod\ndef g():")), ["pkg/mod.py:g"])

    def test_blank_line_inside_function(self):
        self.assertEqual(self._ids(BASE.replace("    x = 1\n", "    x = 1\n\n")), ["pkg/mod.py:f"])

    def test_blank_line_between_functions_is_module_level(self):
        r = self._oracle(BASE.replace("\n\ndef g():", "\n\n\ndef g():"))
        self.assertEqual(sorted(r["nodes"]), ["pkg/mod.py"])

    # ── file đổi tên / file mới ──────────────────────────────────────────────
    def test_renamed_file_uses_old_path_and_reports_rename(self):
        r = self._oracle(BASE.replace("return x", "return x + 1"), rename_to="pkg/mod2.py")
        self.assertEqual(sorted(r["nodes"]), ["pkg/mod.py:f"])
        self.assertEqual(r["renames"], {"pkg/mod.py": "pkg/mod2.py"})

    def test_added_file_is_not_gold(self):
        r = self._oracle(None, extra={"pkg/new.py": "def n():\n    return 1\n"})
        self.assertEqual(r["nodes"], set())
        self.assertEqual(r["added_files"], {"pkg/new.py"})

    def test_two_changes(self):
        new = BASE.replace("a = 1", "a = 2").replace("return 3", "return 4")
        self.assertEqual(self._ids(new), ["pkg/mod.py:A:m1", "pkg/mod.py:g"])

    def test_file_nodes_have_decorator_and_indent(self):
        nodes = {n["id"]: n for n in file_nodes_at(self.repo, self.base, "pkg/mod.py")}
        self.assertEqual((nodes["pkg/mod.py:A:p"]["deco_start"], nodes["pkg/mod.py:A:p"]["start_line"]), (13, 14))
        self.assertEqual(nodes["pkg/mod.py:A:m1"]["indent"], 4)
        self.assertEqual(nodes["pkg/mod.py"]["label"], "Module")


if __name__ == "__main__":
    unittest.main()
