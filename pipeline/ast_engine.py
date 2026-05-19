"""
pipeline/ast_engine.py — AST Engine: parse, scope building, cross-file resolution.

Đây là engine chính của pipeline, phối hợp với SchemaPlugin để tạo đồ thị.

Kiến trúc 3 pass:
─────────────────
Pass 1a (per-file) — _walk_definitions():
    Duyệt AST, emit node Class/Function + cạnh Defines/Imports.
    Kết quả: nodes_out, edges_out (definite edges).

Pass 1b (per-file) — _collect_refs():
    Duyệt AST lần 2, thu thập call sites và inherit refs.
    KHÔNG emit edge ngay — chưa biết endpoint có tồn tại không.
    Kết quả: call_refs_out, inherit_refs_out.

Pass 2 (cross-file, static method) — resolve_cross_file():
    Nhận kết quả của TẤT CẢ files, xây index toàn cục,
    rồi resolve từng ref thành (source, target) cụ thể.
    Kết quả: list cạnh Calls/Inherits (cross-file semantic edges).

Chiến lược resolution (theo thứ tự ưu tiên):
    simple call foo()     → local scope → explicit from-import
    self.method()         → method trong cùng class
    self.x.method()       → type của self.x suy ra từ self.x = TypeName(...)
    module.func()         → module phải là import đã biết; func phải tồn tại trong đó
    ClassName.method()    → class phải local hoặc from-imported; method phải tồn tại
    1-candidate fallback  → chỉ emit khi đúng một candidate trong toàn project
    Còn lại              → bỏ qua (không tạo false-positive edge)
"""

from __future__ import annotations

import logging
import os

from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython

from pipeline.schemas.base import ParseContext, SchemaPlugin

logger = logging.getLogger(__name__)

# ── tree-sitter setup ─────────────────────────────────────────────────────────
# Hai cách khởi tạo Language/Parser tùy version tree-sitter (API thay đổi ở 0.22+)
try:
    PY_LANGUAGE = Language(tspython.language())
    _parser = Parser(PY_LANGUAGE)
except TypeError:
    # tree-sitter < 0.22: constructor khác
    PY_LANGUAGE = Language(tspython.language(), "python")
    _parser = Parser()
    _parser.set_language(PY_LANGUAGE)

# Tên hàm built-in Python — bỏ qua khi tạo call refs để tránh false positive.
# print(x) không nên tạo edge đến node "print" nào trong đồ thị.
_BUILTINS = frozenset({
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
    "tuple", "set", "type", "isinstance", "issubclass", "hasattr", "getattr",
    "setattr", "delattr", "super", "object", "enumerate", "zip", "map",
    "filter", "sorted", "reversed", "min", "max", "sum", "abs", "round",
    "open", "repr", "iter", "next", "any", "all", "vars", "dir", "id",
    "hash", "callable", "staticmethod", "classmethod", "property",
})


class ASTEngine:
    """
    Parser per-file: nhận một file .py, trả về nodes + refs để cross-file resolve.

    Mỗi instance xử lý đúng một file. Chạy song song an toàn (mỗi worker
    tạo instance riêng) vì không có shared state mutable.
    """

    def __init__(
        self,
        file_path: str,
        repo_path: str,
        base_commit: str,
        schema: SchemaPlugin,
    ):
        """
        Args:
            file_path:   Đường dẫn tuyệt đối đến file .py
            repo_path:   Thư mục gốc của repo (để tính relative path)
            base_commit: Commit hash hoặc "local" — prefix của mọi node ID
            schema:      SchemaPlugin instance quyết định label/edge type
        """
        self.file_path   = file_path
        self.repo_path   = repo_path
        self.base_commit = base_commit
        self.schema      = schema

        # Tính relative path để dùng trong node IDs và hiển thị
        try:
            self.rel_path = os.path.relpath(file_path, repo_path).replace("\\", "/")
        except ValueError:
            # Trên Windows, relpath fail nếu khác ổ đĩa — dùng absolute path
            self.rel_path = file_path.replace("\\", "/")

        # module_id là prefix chung cho mọi node trong file này
        # Dạng: "{base_commit}:{rel_path}", vd: "abc123:django/db/models.py"
        self.module_id = f"{self.base_commit}:{self.rel_path}"
        self._directory = os.path.dirname(self.rel_path) or "."
        self._source: bytes = b""  # raw bytes của file — dùng để trích text

        # ── Import tracking ────────────────────────────────────────────────────
        # import X [as Y]        → import_map[Y]    = module_id của X
        # import X.Y             → import_map["X"]  = module_id của X.Y
        self.import_map: dict[str, str] = {}

        # from X import Y [as Z] → from_import_map[Z] = predicted_node_id | None
        # None khi X là external library (không trong repo)
        self.from_import_map: dict[str, str | None] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(self) -> dict | None:
        """
        Parse file và trả về dict kết quả để cross-file resolution dùng.

        Returns None nếu không đọc được file hoặc tree-sitter lỗi.

        Kết quả (dict) gồm:
            module_id, nodes, definite_edges,
            call_refs, inherit_refs, instance_attr_types,
            import_map, from_import_map,
            local_scope, class_scopes
        """
        # Đọc file dạng bytes — tree-sitter làm việc với raw bytes
        try:
            with open(self.file_path, "rb") as f:
                self._source = f.read()
        except Exception as e:
            logger.warning(f"Cannot read {self.file_path}: {e}")
            return None

        # Parse AST
        try:
            tree = _parser.parse(self._source)
        except Exception as e:
            logger.warning(f"tree-sitter error {self.file_path}: {e}")
            return None

        # Tạo ParseContext gốc — các context con chia sẻ các list *_out này
        ctx = ParseContext(
            module_id=self.module_id,
            parent_id=self.module_id,
            in_class=False,
            is_module_scope=True,
            current_class_id=None,
            text_of=self._text,  # inject hàm trích text vào context
        )

        # Mọi schema đều có đúng một Module node per file
        ctx.emit_node("Module", self.module_id, {
            "name":   self.rel_path,
            "commit": self.base_commit,
        })

        # ── Pass 1a: definitions + imports ────────────────────────────────────
        self._walk_definitions(tree.root_node, ctx)
        self._walk_imports(tree.root_node, ctx)
        # Xây scope tables để dùng trong Pass 2 resolve
        local_scope, class_scopes = self._build_scopes(ctx.nodes_out)

        # ── Pass 1b: ref collection ───────────────────────────────────────────
        self._collect_refs(tree.root_node, ctx, local_types={})

        return {
            "module_id":            self.module_id,
            "nodes":                ctx.nodes_out,
            "definite_edges":       ctx.edges_out,
            "call_refs":            ctx.call_refs_out,
            "inherit_refs":         ctx.inherit_refs_out,
            "instance_attr_types":  ctx.instance_attr_types_out,
            "import_map":           self.import_map,
            "from_import_map":      self.from_import_map,
            "local_scope":          local_scope,
            "class_scopes":         class_scopes,
        }

    # ── Pass 1a: definition walk ──────────────────────────────────────────────

    def _walk_definitions(self, node: Node, ctx: ParseContext) -> None:
        """
        Duyệt AST đệ quy, emit node và cạnh cho mọi class/function.

        Khi vào class/function: tạo context con với parent_id cập nhật.
        Điều này đảm bảo nested class hoặc nested function có ID đúng.
        """
        for child in node.children:
            if child.type == "class_definition":
                # Schema quyết định label ("Class" hay "CLASS") và emit node
                new_id = self.schema.on_class(child, ctx)
                child_ctx = ParseContext(
                    module_id=ctx.module_id,
                    # parent_id chuyển sang class id mới nếu schema đã emit node
                    parent_id=new_id if new_id else ctx.parent_id,
                    in_class=True,
                    is_module_scope=False,
                    current_class_id=new_id if new_id else ctx.current_class_id,
                    # Chia sẻ output lists với context cha
                    nodes_out=ctx.nodes_out,
                    edges_out=ctx.edges_out,
                    call_refs_out=ctx.call_refs_out,
                    inherit_refs_out=ctx.inherit_refs_out,
                    instance_attr_types_out=ctx.instance_attr_types_out,
                    text_of=ctx.text_of,
                )
                self._walk_definitions(child, child_ctx)

            elif child.type in ("function_definition", "async_function_definition"):
                new_id = self.schema.on_function(child, ctx)
                child_ctx = ParseContext(
                    module_id=ctx.module_id,
                    parent_id=new_id if new_id else ctx.parent_id,
                    in_class=ctx.in_class,       # giữ nguyên — function có thể trong class
                    is_module_scope=False,
                    current_class_id=ctx.current_class_id,
                    nodes_out=ctx.nodes_out,
                    edges_out=ctx.edges_out,
                    call_refs_out=ctx.call_refs_out,
                    inherit_refs_out=ctx.inherit_refs_out,
                    instance_attr_types_out=ctx.instance_attr_types_out,
                    text_of=ctx.text_of,
                )
                self._walk_definitions(child, child_ctx)

            else:
                # Với mọi node khác: tiếp tục đệ quy với context hiện tại
                self._walk_definitions(child, ctx)

    # ── Pass 1a: imports ──────────────────────────────────────────────────────

    def _walk_imports(self, node: Node, ctx: ParseContext) -> None:
        """
        Duyệt toàn bộ AST (dùng DFS stack) để tìm import statements.

        Xử lý hai dạng:
          - `import X [as Y]`      → emit Imports edge + ghi import_map
          - `from X import Y [as Z]` → emit Imports edge + ghi from_import_map
        """
        for child in self._iter_all(node):
            if child.type == "import_statement":
                # `import os`, `import django.db`, `import numpy as np`
                for sub in child.children:
                    if sub.type in ("dotted_name", "aliased_import"):
                        raw = self._text(sub)
                        mod_str, _, alias = raw.partition(" as ")
                        mod_str = mod_str.strip()
                        alias = alias.strip() if alias.strip() else mod_str.split(".")[-1]
                        tid = self._resolve_module(mod_str)
                        if tid:
                            # Chỉ emit edge nếu module nằm trong repo
                            self.schema.on_import(tid, ctx)
                            self.import_map[alias] = tid
                            if "." in mod_str:
                                # `import django.db` → cả "django" lẫn "django.db" map đến tid
                                self.import_map[mod_str] = tid

            elif child.type == "import_from_statement":
                # `from django.db import models`
                mod_node = child.child_by_field_name("module_name")
                if not mod_node:
                    continue
                mod_str = self._text(mod_node)
                module_tid = self._resolve_module(mod_str)
                if module_tid:
                    self.schema.on_import(module_tid, ctx)

                # Xử lý từng tên được import: `from X import Y, Z as W`
                for local_name, orig_name in self._get_from_imports(child):
                    # Kiểm tra xem Y có phải là sub-module không (vd: from pkg import submod)
                    sub_tid = self._resolve_module(f"{mod_str}.{orig_name}")
                    if sub_tid:
                        self.import_map[local_name] = sub_tid
                    elif module_tid:
                        # Dự đoán node ID: "{module_tid}:{orig_name}"
                        # Sẽ được verify ở Pass 2 (kiểm tra có trong all_node_ids không)
                        self.from_import_map[local_name] = f"{module_tid}:{orig_name}"
                    else:
                        # External import (os, sys, ...) — ghi None để biết đã xử lý
                        self.from_import_map[local_name] = None

    def _get_from_imports(self, from_stmt: Node) -> list[tuple[str, str]]:
        """
        Parse danh sách tên trong `from X import ...`.

        Trả về list (local_name, original_name):
          - `from X import Y`      → [("Y", "Y")]
          - `from X import Y as Z` → [("Z", "Y")]
          - `from X import Y, Z`   → [("Y", "Y"), ("Z", "Z")]
        """
        results: list[tuple[str, str]] = []
        past_import = False  # flag: đã qua keyword "import" chưa

        for child in from_stmt.children:
            if child.type == "import":
                past_import = True
                continue
            if not past_import:
                continue
            if child.type == "wildcard_import":
                # `from X import *` — không thể resolve cụ thể, bỏ qua
                break
            if child.type == "identifier":
                name = self._text(child)
                results.append((name, name))
            elif child.type == "import_as_names":
                # `from X import Y, Z as W`
                for sub in child.children:
                    if sub.type == "identifier":
                        name = self._text(sub)
                        results.append((name, name))
                    elif sub.type == "aliased_import":
                        orig  = sub.child_by_field_name("name")
                        alias = sub.child_by_field_name("alias")
                        if orig:
                            o = self._text(orig)
                            a = self._text(alias) if alias else o
                            results.append((a, o))
            elif child.type == "aliased_import":
                # `from X import Y as Z`
                orig  = child.child_by_field_name("name")
                alias = child.child_by_field_name("alias")
                if orig:
                    o = self._text(orig)
                    a = self._text(alias) if alias else o
                    results.append((a, o))
        return results

    def _resolve_module(self, module: str) -> str | None:
        """
        Tìm file .py tương ứng với tên module, trả về module_id nếu tồn tại.

        Xử lý cả relative import (bắt đầu bằng '.') lẫn absolute import.
        Kiểm tra cả {module}.py lẫn {module}/__init__.py.

        Trả về None nếu module là external (không trong repo).
        """
        if module.startswith("."):
            # Relative import: `.models` → ../models.py, `..utils` → ../../utils.py
            dots     = len(module) - len(module.lstrip("."))
            rel_part = module.lstrip(".")
            base_dir = os.path.dirname(self.rel_path)
            # Đi lên dot-1 cấp (1 dot = cùng package, 2 dots = package cha)
            for _ in range(dots - 1):
                base_dir = os.path.dirname(base_dir)
            parts = (
                os.path.join(base_dir, rel_part.replace(".", os.sep)).replace("\\", "/")
                if rel_part
                else base_dir
            )
        else:
            # Absolute import: `django.db.models` → `django/db/models`
            parts = module.replace(".", "/")

        # Thử cả dạng module.py và package/__init__.py
        for candidate in (f"{parts}.py", f"{parts}/__init__.py"):
            full = os.path.join(self.repo_path, candidate)
            if os.path.exists(full):
                rel = os.path.relpath(full, self.repo_path).replace("\\", "/")
                return f"{self.base_commit}:{rel}"

        return None  # external library

    # ── Pass 1b: ref collection ───────────────────────────────────────────────

    def _collect_refs(
        self,
        node: Node,
        ctx: ParseContext,
        local_types: dict[str, str],
    ) -> None:
        """
        Duyệt AST lần 2, thu thập call refs và inherit refs.

        local_types: {variable_name → type_name} cho scope hiện tại.
        Được cập nhật khi gặp assignment `x = TypeName(...)` hoặc type annotation.
        Giúp resolve `x.method()` → TypeName.method().
        """
        for child in node.children:
            if child.type == "class_definition":
                name = self._field(child, "name")
                class_id = f"{ctx.module_id}:{name}" if name else ctx.parent_id

                # Thu thập superclass refs
                supers = child.child_by_field_name("superclasses")
                if supers:
                    for arg in supers.children:
                        base = self._extract_base_name(arg)
                        if base:
                            self.schema.on_inherit(child, ctx, base)
                            ctx.inherit_refs_out.append({
                                "class_id":  class_id,
                                "base_name": base,
                            })

                # Context mới cho class body: local_types reset (class scope riêng)
                child_ctx = ParseContext(
                    module_id=ctx.module_id,
                    parent_id=class_id,
                    in_class=True,
                    is_module_scope=False,
                    current_class_id=class_id,
                    nodes_out=ctx.nodes_out,
                    edges_out=ctx.edges_out,
                    call_refs_out=ctx.call_refs_out,
                    inherit_refs_out=ctx.inherit_refs_out,
                    instance_attr_types_out=ctx.instance_attr_types_out,
                    text_of=ctx.text_of,
                )
                self._collect_refs(child, child_ctx, local_types={})

            elif child.type in ("function_definition", "async_function_definition"):
                name    = self._field(child, "name")
                func_id = f"{ctx.parent_id}:{name}" if name else ctx.parent_id

                # Copy local_types từ outer scope + thêm type hints từ params
                func_locals = local_types.copy()
                self._extract_params_types(child, func_locals)

                child_ctx = ParseContext(
                    module_id=ctx.module_id,
                    parent_id=func_id,
                    in_class=ctx.in_class,
                    is_module_scope=False,
                    current_class_id=ctx.current_class_id,
                    nodes_out=ctx.nodes_out,
                    edges_out=ctx.edges_out,
                    call_refs_out=ctx.call_refs_out,
                    inherit_refs_out=ctx.inherit_refs_out,
                    instance_attr_types_out=ctx.instance_attr_types_out,
                    text_of=ctx.text_of,
                )
                self._collect_refs(child, child_ctx, func_locals)

            elif child.type == "call":
                self._handle_call(child, ctx, local_types)
                # Tiếp tục duyệt trong call (có thể có call lồng nhau)
                self._collect_refs(child, ctx, local_types)

            elif child.type in ("assignment", "annotated_assignment", "expression_statement"):
                # Xử lý assignment để cập nhật local_types và emit FIELD/GLOBAL_VAR
                target_node = child
                if child.type == "expression_statement" and child.child_count > 0:
                    if child.children[0].type == "assignment":
                        target_node = child.children[0]

                if target_node.type == "assignment":
                    self._collect_local_assignment(target_node, ctx, local_types)
                elif target_node.type == "annotated_assignment":
                    self._collect_ann_assignment(target_node, local_types)

                # Cho schema emit FIELD/GLOBAL_VARIABLE nếu cần
                self.schema.on_assignment(target_node, ctx)
                self._collect_refs(child, ctx, local_types)

            else:
                self._collect_refs(child, ctx, local_types)

    def _handle_call(
        self, call_node: Node, ctx: ParseContext, local_types: dict[str, str]
    ) -> None:
        """Trích call ref từ call node và thêm vào call_refs_out nếu resolve được."""
        ref = self._extract_call_ref(
            call_node, ctx.parent_id, ctx.current_class_id, local_types
        )
        if ref is not None:
            self.schema.on_call(call_node, ctx)
            ctx.call_refs_out.append(ref)

    def _extract_call_ref(
        self,
        call_node: Node,
        caller_id: str,
        current_class_id: str | None,
        local_types: dict[str, str],
    ) -> dict | None:
        """
        Phân tích cú pháp call expression và trả về ref dict mô tả call đó.

        Phân loại call thành các "kind":
          "simple"          — foo()
          "self_method"     — self.method() / cls.method()
          "self_attr_method"— self.x.method() (cần resolve type của self.x)
          "local_method"    — x.method() khi x có type hint/assignment
          "attr"            — obj.method() (chung, kém chắc hơn)

        Trả về None cho built-ins và call phức tạp không resolve được.
        """
        func = call_node.child_by_field_name("function")
        if func is None:
            return None

        # Thông tin chung cho mọi ref
        base = {
            "caller_id": caller_id,
            "line":      call_node.start_point[0] + 1,
            "file":      self.rel_path,
        }

        if func.type == "identifier":
            # Trường hợp đơn giản: foo()
            name = self._text(func)
            if name in _BUILTINS:
                return None  # bỏ qua built-in calls
            return {**base, "kind": "simple", "name": name}

        if func.type == "attribute":
            obj  = func.child_by_field_name("object")
            attr = func.child_by_field_name("attribute")
            if obj is None or attr is None:
                return None
            attr_name = self._text(attr)
            if attr_name in _BUILTINS:
                return None

            obj_text = self._text(obj)

            if obj_text in ("self", "cls"):
                # self.method() — resolve trong class scope
                return {**base, "kind": "self_method", "name": attr_name, "class_id": current_class_id}

            if obj.type == "attribute":
                # self.x.method() — cần biết type của self.x
                inner_obj  = obj.child_by_field_name("object")
                inner_attr = obj.child_by_field_name("attribute")
                if inner_obj and inner_attr and self._text(inner_obj) in ("self", "cls"):
                    return {
                        **base,
                        "kind":     "self_attr_method",
                        "name":     attr_name,
                        "attr":     self._text(inner_attr),
                        "class_id": current_class_id,
                    }

            if obj_text in local_types:
                # x.method() khi biết type của x từ annotation hoặc assignment
                return {**base, "kind": "local_method", "name": attr_name, "type_name": local_types[obj_text]}

            # Trường hợp chung: module.func() hoặc obj.method() không rõ type
            return {**base, "kind": "attr", "name": attr_name, "obj": obj_text}

        return None  # call expression phức tạp khác (vd: (lambda: x)())

    def _collect_local_assignment(
        self, node: Node, ctx: ParseContext, local_types: dict[str, str]
    ) -> None:
        """
        Cập nhật local_types từ assignment `x = TypeName(...)`.

        Hai trường hợp:
          1. `self.x = TypeName(...)` → ghi vào instance_attr_types_out
             để resolve `self.x.method()` sau này
          2. `x = TypeName(...)` → ghi vào local_types cho scope hiện tại
        """
        left  = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or right.type != "call":
            return

        func = right.child_by_field_name("function")
        if func is None:
            return

        # Trích tên type: `TypeName(...)` hoặc `module.TypeName(...)`
        type_name = None
        if func.type == "identifier":
            type_name = self._text(func)
        elif func.type == "attribute":
            type_attr = func.child_by_field_name("attribute")
            type_name = self._text(type_attr) if type_attr else None

        if not type_name or type_name in _BUILTINS:
            return  # bỏ qua `x = list()`, `x = dict()`, ...

        if left.type == "attribute" and ctx.current_class_id:
            # self.x = TypeName(...) trong class
            obj_node  = left.child_by_field_name("object")
            attr_node = left.child_by_field_name("attribute")
            if obj_node and attr_node and self._text(obj_node) in ("self", "cls"):
                ctx.instance_attr_types_out.append({
                    "class_id":  ctx.current_class_id,
                    "attr":      self._text(attr_node),
                    "type_name": type_name,
                })
        elif left.type == "identifier":
            # x = TypeName(...) — ghi vào local scope hiện tại
            local_types[self._text(left)] = type_name

    def _collect_ann_assignment(self, node: Node, local_types: dict[str, str]) -> None:
        """Cập nhật local_types từ annotated assignment `x: TypeName = ...`."""
        target    = node.child_by_field_name("target")
        type_node = node.child_by_field_name("type")
        if not target or not type_node:
            return
        type_name = self._extract_base_name(type_node)
        if not type_name:
            return
        if target.type == "identifier":
            local_types[self._text(target)] = type_name

    def _extract_params_types(self, func_node: Node, local_types: dict[str, str]) -> None:
        """
        Trích type hints từ function parameters vào local_types.

        Ví dụ: `def foo(x: MyClass)` → local_types["x"] = "MyClass"
        Giúp resolve `x.method()` trong thân hàm.
        """
        params = func_node.child_by_field_name("parameters")
        if not params:
            return
        for param in params.children:
            if param.type == "typed_parameter":
                name_node = param.child_by_field_name("name")
                type_node = param.child_by_field_name("type")
                if name_node and type_node:
                    local_types[self._text(name_node)] = self._extract_base_name(type_node)

    # ── Scope building ────────────────────────────────────────────────────────

    def _build_scopes(
        self, nodes: list[dict]
    ) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        """
        Xây dựng scope tables từ danh sách nodes đã emit.

        local_scope:  {name → node_id} cho mọi Class/Function ở module level
        class_scopes: {class_id → {method_name → method_id}} cho method lookup

        Hai tables này được dùng trong Pass 2 cross-file resolution để
        resolve `from module import Foo` → tìm node Foo trong module đó.
        """
        local_scope:  dict[str, str] = {}
        class_scopes: dict[str, dict[str, str]] = {}

        for node in nodes:
            label   = node["labels"][0]
            if label == "Module":
                continue  # Module node không cần scope

            node_id = node["id"]
            name    = node["properties"].get("name", "")
            # Trích phần ID sau module_id prefix để xác định depth
            parts   = node_id[len(self.module_id):].lstrip(":").split(":")

            if len(parts) == 1:
                # Depth 1: Class hoặc Function trực tiếp trong module
                local_scope[name] = node_id
            elif len(parts) == 2 and label in ("Function", "METHOD"):
                # Depth 2: Method trong class
                class_id = f"{self.module_id}:{parts[0]}"
                class_scopes.setdefault(class_id, {})[name] = node_id

        return local_scope, class_scopes

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _text(self, node: Node) -> str:
        """Trích text của node từ raw bytes source."""
        return self._source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _field(self, node: Node, field: str) -> str:
        """Trích text của một named field trong node (vd: field="name" của class_definition)."""
        child = node.child_by_field_name(field)
        return self._text(child) if child else ""

    def _iter_all(self, node: Node):
        """DFS iterator qua toàn bộ cây con (dùng stack thay đệ quy để tránh stack overflow)."""
        stack = [node]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(reversed(n.children))  # reversed để duyệt trái-trước

    def _extract_base_name(self, node: Node) -> str:
        """
        Trích tên type từ các dạng type expression khác nhau.

        identifier   → "MyClass"
        attribute    → lấy phần attribute (vd: "models.Model" → "Model")
        subscript    → lấy base (vd: "Optional[int]" → "Optional")
        type         → delegate xuống child đầu tiên
        """
        if node.type == "identifier":
            return self._text(node)
        if node.type == "attribute":
            attr = node.child_by_field_name("attribute")
            return self._text(attr) if attr else ""
        if node.type == "subscript":
            val = node.child_by_field_name("value")
            return self._extract_base_name(val) if val else ""
        if node.type == "type":
            return self._extract_base_name(node.children[0]) if node.child_count > 0 else ""
        return ""

    # ── Pass 2: cross-file resolution (static) ───────────────────────────────

    @staticmethod
    def resolve_cross_file(all_results: list[dict], schema: SchemaPlugin) -> list[dict]:
        """
        Resolve tất cả call refs và inherit refs thành cạnh cụ thể.

        Nhận kết quả parse của MỌI file trong repo, xây các index toàn cục,
        rồi với mỗi ref tìm node đích.

        Chiến lược "không false-positive":
          - Chỉ emit edge khi resolve được chính xác
          - Fallback 1-candidate: chỉ emit khi đúng một candidate trong project

        Returns:
            list[dict]: danh sách cạnh semantic (Calls, Inherits) cross-file
        """
        # ── Xây index toàn cục trong một lần duyệt ───────────────────────────
        all_node_ids:      set[str]                  = set()
        all_class_scopes:  dict[str, dict[str, str]] = {}
        instance_attr_map: dict[tuple, list[str]]    = {}
        file_data:         dict[str, dict]           = {}
        # global_name_scope: name → [node_id] — tất cả module-level definitions
        global_name_scope: dict[str, list[str]]      = {}

        for r in all_results:
            file_data[r["module_id"]] = r
            for n in r["nodes"]:
                all_node_ids.add(n["id"])
            all_class_scopes.update(r.get("class_scopes", {}))
            # Gom self.x = Type(...) assignments theo (class_id, attr)
            for entry in r.get("instance_attr_types", []):
                key = (entry["class_id"], entry["attr"])
                instance_attr_map.setdefault(key, []).append(entry["type_name"])
            # Gom mọi module-level name để dùng unique-candidate fallback
            for name, nid in r.get("local_scope", {}).items():
                global_name_scope.setdefault(name, []).append(nid)

        # ── Xây inheritance map (cần all_node_ids đã đầy đủ) ─────────────────
        inheritance_map: dict[str, list[str]] = {}
        for r in all_results:
            fmap   = r.get("from_import_map", {})
            lscope = r.get("local_scope", {})
            for ref in r.get("inherit_refs", []):
                for base_id in ASTEngine._resolve_name(
                    ref["base_name"], fmap, lscope, all_node_ids
                ):
                    inheritance_map.setdefault(ref["class_id"], []).append(base_id)

        # ── Resolve từng call ref ─────────────────────────────────────────────
        edges: list[dict] = []
        seen:  set[tuple] = set()  # dedup (source, target, type)
        resolved = unresolved = 0
        total_refs = sum(len(r.get("call_refs", [])) for r in all_results)
        logger.info(f"Resolving {total_refs} refs...")

        for result in all_results:
            import_map      = result.get("import_map", {})
            from_import_map = result.get("from_import_map", {})
            local_scope     = result.get("local_scope", {})
            class_scopes    = result.get("class_scopes", {})

            for ref in result.get("call_refs", []):
                caller_id = ref["caller_id"]
                targets = ASTEngine._resolve_call(
                    ref, import_map, from_import_map, local_scope, class_scopes,
                    file_data, all_node_ids, all_class_scopes, instance_attr_map,
                    inheritance_map, global_name_scope,
                )
                if targets:
                    resolved += 1
                else:
                    unresolved += 1

                for target_id in targets:
                    key = (caller_id, target_id, schema.call_edge_type)
                    if caller_id != target_id and key not in seen:
                        seen.add(key)
                        edges.append({
                            "type":   schema.call_edge_type,
                            "source": caller_id,
                            "target": target_id,
                            "line":   ref["line"],
                        })

            # Resolve inherit refs (cũng dùng _resolve_name)
            for ref in result.get("inherit_refs", []):
                class_id  = ref["class_id"]
                base_name = ref["base_name"]
                fmap   = result.get("from_import_map", {})
                lscope = result.get("local_scope", {})
                for target_id in ASTEngine._resolve_name(base_name, fmap, lscope, all_node_ids):
                    key = (class_id, target_id, schema.inherit_edge_type)
                    if class_id != target_id and key not in seen:
                        seen.add(key)
                        edges.append({
                            "type":   schema.inherit_edge_type,
                            "source": class_id,
                            "target": target_id,
                        })

        logger.info(f"Resolved: {resolved}, Unresolved: {unresolved}")
        return edges

    @staticmethod
    def _resolve_call(
        ref: dict,
        import_map: dict,
        from_import_map: dict,
        local_scope: dict,
        class_scopes: dict,
        file_data: dict,
        all_node_ids: set,
        all_class_scopes: dict,
        instance_attr_map: dict,
        inheritance_map: dict,
        global_name_scope: dict | None = None,
    ) -> list[str]:
        """
        Resolve một call ref thành danh sách node_id đích.

        Thường trả về list 1 phần tử. Trả về [] nếu không resolve được.
        Không bao giờ emit edge khi ambiguous (nhiều candidate).
        """
        kind      = ref["kind"]
        func_name = ref["name"]

        if kind == "simple":
            # foo() — tìm trong local scope rồi from_import_map
            resolved = ASTEngine._resolve_name(func_name, from_import_map, local_scope, all_node_ids)
            if resolved:
                return resolved
            # Fallback: tìm trong toàn project — chỉ emit khi unique
            if global_name_scope:
                candidates = [
                    nid for nid in global_name_scope.get(func_name, [])
                    if nid in all_node_ids and nid not in local_scope.values()
                ]
                unique = list(set(candidates))
                if len(unique) == 1:
                    return unique
            return []

        candidates = []
        if kind == "self_method":
            # self.method() → class hiện tại
            candidates = [ref.get("class_id")]

        elif kind == "self_attr_method":
            # self.x.method() → resolve type của self.x trước
            class_id  = ref.get("class_id")
            attr_name = ref.get("attr")
            if class_id and attr_name:
                type_names = ASTEngine._find_attr_type_recursive(
                    class_id, attr_name, instance_attr_map, inheritance_map, set()
                )
                for tn in type_names:
                    candidates.extend(
                        ASTEngine._resolve_name(tn, from_import_map, local_scope, all_node_ids)
                    )

        elif kind == "local_method":
            # x.method() khi biết type của x
            type_name  = ref.get("type_name")
            candidates = ASTEngine._resolve_name(type_name, from_import_map, local_scope, all_node_ids)

        elif kind == "attr":
            # obj.func() — kiểm tra xem obj có phải là imported module không
            obj_name  = ref["obj"]
            module_id = import_map.get(obj_name)
            if module_id and module_id in file_data:
                target = file_data[module_id]
                nid = target.get("local_scope", {}).get(func_name)
                if not nid:
                    # Thử from_import_map của module đó
                    predicted = target.get("from_import_map", {}).get(func_name)
                    if predicted and predicted in all_node_ids:
                        nid = predicted
                if nid:
                    return [nid]
            candidates = ASTEngine._resolve_name(obj_name, from_import_map, local_scope, all_node_ids)

        # Tìm method trong class candidates và inheritance chain
        for start_class_id in candidates:
            if not start_class_id:
                continue
            nid = ASTEngine._find_method_recursive(
                start_class_id, func_name, all_class_scopes, inheritance_map, set()
            )
            if nid:
                return [nid]

        # 1-candidate fallback cho các kind không-simple
        if kind in ("self_attr_method", "local_method", "attr"):
            matches = []
            potential_classes = list(from_import_map.values()) + list(local_scope.values())
            for cid in potential_classes:
                if cid and cid in all_class_scopes:
                    nid = ASTEngine._find_method_recursive(
                        cid, func_name, all_class_scopes, inheritance_map, set()
                    )
                    if nid:
                        matches.append(nid)
            if len(set(matches)) == 1:
                return [matches[0]]

        return []

    @staticmethod
    def _resolve_name(
        name: str,
        from_import_map: dict,
        local_scope: dict,
        all_node_ids: set,
    ) -> list[str]:
        """
        Resolve tên thành node_id bằng cách tra cứu local scope rồi from_import_map.

        Kiểm tra all_node_ids để loại bỏ predicted IDs không thực sự tồn tại.
        """
        # Ưu tiên local scope (tránh nhầm với import trùng tên)
        nid = local_scope.get(name)
        if nid and nid in all_node_ids:
            return [nid]
        # Fallback: from_import_map (predicted ID)
        predicted = from_import_map.get(name)
        if predicted and predicted in all_node_ids:
            return [predicted]
        return []

    @staticmethod
    def _find_method_recursive(
        class_id: str,
        method_name: str,
        all_class_scopes: dict,
        inheritance_map: dict,
        visited: set,
    ) -> str | None:
        """
        Tìm method trong class và toàn bộ inheritance chain (DFS).

        visited ngăn infinite loop khi có diamond inheritance hoặc circular.
        """
        if class_id in visited:
            return None
        visited.add(class_id)

        # Tìm trong class này trước
        nid = all_class_scopes.get(class_id, {}).get(method_name)
        if nid:
            return nid

        # Đệ quy lên parent classes
        for base_id in inheritance_map.get(class_id, []):
            found = ASTEngine._find_method_recursive(
                base_id, method_name, all_class_scopes, inheritance_map, visited
            )
            if found:
                return found

        return None

    @staticmethod
    def _find_attr_type_recursive(
        class_id: str,
        attr_name: str,
        instance_attr_map: dict,
        inheritance_map: dict,
        visited: set,
    ) -> list[str]:
        """
        Tìm type của instance attribute trong class và inheritance chain.

        Dùng để resolve `self.x.method()`:
          1. Tìm `self.x = TypeName(...)` trong class hoặc parent class
          2. Trả về ["TypeName"] để caller tiếp tục resolve TypeName.method()
        """
        if class_id in visited:
            return []
        visited.add(class_id)

        types = instance_attr_map.get((class_id, attr_name), [])
        if types:
            return types

        # Tìm trong parent classes (MRO đơn giản — không theo C3 linearization)
        for parent_id in inheritance_map.get(class_id, []):
            res = ASTEngine._find_attr_type_recursive(
                parent_id, attr_name, instance_attr_map, inheritance_map, visited
            )
            if res:
                return res

        return []
