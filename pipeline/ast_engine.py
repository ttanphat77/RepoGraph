"""
AST Engine — language-level parsing, scope building, and cross-file resolution.

Responsibilities
----------------
- Read and parse a single Python file with tree-sitter.
- Walk the AST and dispatch events to a SchemaPlugin.
- Build import maps and scope tables needed for cross-file resolution.
- Resolve call and inheritance refs across all files (static method).

What does NOT live here
-----------------------
- Which node labels or edge types to emit  →  SchemaPlugin
- Any graph-schema-specific naming              →  SchemaPlugin

Resolution strategy (in priority order):
  simple call foo()       → local scope → explicit from-import
  self.method()           → same class methods only
  self.x.method()         → type of self.x inferred from self.x = TypeName(...)
  module.func()           → module must be a known import; func must exist in it
  ClassName.method()      → class must be local or from-imported; method exists in it
  1-candidate fallback    → only when exactly one class in scope has that method
  everything else         → dropped (no false positives)
"""

from __future__ import annotations

import logging
import os
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython

from pipeline.schemas.base import ParseContext, SchemaPlugin

logger = logging.getLogger(__name__)

try:
    PY_LANGUAGE = Language(tspython.language())
    _parser = Parser(PY_LANGUAGE)
except TypeError:
    PY_LANGUAGE = Language(tspython.language(), "python")
    _parser = Parser()
    _parser.set_language(PY_LANGUAGE)

_BUILTINS = frozenset({
    "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
    "tuple", "set", "type", "isinstance", "issubclass", "hasattr", "getattr",
    "setattr", "delattr", "super", "object", "enumerate", "zip", "map",
    "filter", "sorted", "reversed", "min", "max", "sum", "abs", "round",
    "open", "repr", "iter", "next", "any", "all", "vars", "dir", "id",
    "hash", "callable", "staticmethod", "classmethod", "property",
})


class ASTEngine:
    def __init__(
        self,
        file_path: str,
        repo_path: str,
        base_commit: str,
        schema: SchemaPlugin,
    ):
        self.file_path = file_path
        self.repo_path = repo_path
        self.base_commit = base_commit
        self.schema = schema

        try:
            self.rel_path = os.path.relpath(file_path, repo_path).replace("\\", "/")
        except ValueError:
            self.rel_path = file_path.replace("\\", "/")

        self.module_id = f"{self.base_commit}:{self.rel_path}"
        self._directory = os.path.dirname(self.rel_path) or "."
        self._source: bytes = b""

        # import X [as Y]        → import_map[Y]    = module_id
        # import X.Y             → import_map["X"]  = module_id
        self.import_map: dict[str, str] = {}

        # from X import Y [as Z] → from_import_map[Z] = predicted_node_id | None
        self.from_import_map: dict[str, str | None] = {}

    # ── public ────────────────────────────────────────────────────────────────

    def parse(self) -> dict | None:
        try:
            with open(self.file_path, "rb") as f:
                self._source = f.read()
        except Exception as e:
            logger.warning(f"Cannot read {self.file_path}: {e}")
            return None

        try:
            tree = _parser.parse(self._source)
        except Exception as e:
            logger.warning(f"tree-sitter error {self.file_path}: {e}")
            return None

        ctx = ParseContext(
            module_id=self.module_id,
            parent_id=self.module_id,
            in_class=False,
            is_module_scope=True,
            current_class_id=None,
            text_of=self._text,
        )

        # Emit the Module node directly — every schema has exactly one per file
        ctx.emit_node("Module", self.module_id, {
            "name": self.rel_path,
            "commit": self.base_commit,
        })

        # Pass 1: definitions + imports
        self._walk_definitions(tree.root_node, ctx)
        self._walk_imports(tree.root_node, ctx)
        local_scope, class_scopes = self._build_scopes(ctx.nodes_out)

        # Pass 2: collect refs (calls, inheritance, assignments)
        self._collect_refs(tree.root_node, ctx, local_types={})

        return {
            "module_id": self.module_id,
            "nodes": ctx.nodes_out,
            "definite_edges": ctx.edges_out,
            "call_refs": ctx.call_refs_out,
            "inherit_refs": ctx.inherit_refs_out,
            "instance_attr_types": ctx.instance_attr_types_out,
            "import_map": self.import_map,
            "from_import_map": self.from_import_map,
            "local_scope": local_scope,
            "class_scopes": class_scopes,
        }

    # ── pass 1: definition walk ───────────────────────────────────────────────

    def _walk_definitions(self, node: Node, ctx: ParseContext) -> None:
        for child in node.children:
            if child.type == "class_definition":
                new_id = self.schema.on_class(child, ctx)
                child_ctx = ParseContext(
                    module_id=ctx.module_id,
                    parent_id=new_id if new_id else ctx.parent_id,
                    in_class=True,
                    is_module_scope=False,
                    current_class_id=new_id if new_id else ctx.current_class_id,
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
                self._walk_definitions(child, child_ctx)

            else:
                self._walk_definitions(child, ctx)

    # ── pass 1: imports ───────────────────────────────────────────────────────

    def _walk_imports(self, node: Node, ctx: ParseContext) -> None:
        for child in self._iter_all(node):
            if child.type == "import_statement":
                for sub in child.children:
                    if sub.type in ("dotted_name", "aliased_import"):
                        raw = self._text(sub)
                        mod_str, _, alias = raw.partition(" as ")
                        mod_str = mod_str.strip()
                        alias = alias.strip() if alias.strip() else mod_str.split(".")[-1]
                        tid = self._resolve_module(mod_str)
                        if tid:
                            self.schema.on_import(tid, ctx)
                            self.import_map[alias] = tid
                            if "." in mod_str:
                                self.import_map[mod_str] = tid

            elif child.type == "import_from_statement":
                mod_node = child.child_by_field_name("module_name")
                if not mod_node:
                    continue
                mod_str = self._text(mod_node)
                module_tid = self._resolve_module(mod_str)
                if module_tid:
                    self.schema.on_import(module_tid, ctx)

                for local_name, orig_name in self._get_from_imports(child):
                    sub_tid = self._resolve_module(f"{mod_str}.{orig_name}")
                    if sub_tid:
                        self.import_map[local_name] = sub_tid
                    elif module_tid:
                        self.from_import_map[local_name] = f"{module_tid}:{orig_name}"
                    else:
                        self.from_import_map[local_name] = None

    def _get_from_imports(self, from_stmt: Node) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        past_import = False
        for child in from_stmt.children:
            if child.type == "import":
                past_import = True
                continue
            if not past_import:
                continue
            if child.type == "wildcard_import":
                break
            if child.type == "identifier":
                name = self._text(child)
                results.append((name, name))
            elif child.type == "import_as_names":
                for sub in child.children:
                    if sub.type == "identifier":
                        name = self._text(sub)
                        results.append((name, name))
                    elif sub.type == "aliased_import":
                        orig = sub.child_by_field_name("name")
                        alias = sub.child_by_field_name("alias")
                        if orig:
                            o = self._text(orig)
                            a = self._text(alias) if alias else o
                            results.append((a, o))
            elif child.type == "aliased_import":
                orig = child.child_by_field_name("name")
                alias = child.child_by_field_name("alias")
                if orig:
                    o = self._text(orig)
                    a = self._text(alias) if alias else o
                    results.append((a, o))
        return results

    def _resolve_module(self, module: str) -> str | None:
        if module.startswith("."):
            dots = len(module) - len(module.lstrip("."))
            rel_part = module.lstrip(".")
            base_dir = os.path.dirname(self.rel_path)
            for _ in range(dots - 1):
                base_dir = os.path.dirname(base_dir)
            parts = (
                os.path.join(base_dir, rel_part.replace(".", os.sep)).replace("\\", "/")
                if rel_part
                else base_dir
            )
        else:
            parts = module.replace(".", "/")

        for candidate in (f"{parts}.py", f"{parts}/__init__.py"):
            full = os.path.join(self.repo_path, candidate)
            if os.path.exists(full):
                rel = os.path.relpath(full, self.repo_path).replace("\\", "/")
                return f"{self.base_commit}:{rel}"
        return None

    # ── pass 2: ref collection ────────────────────────────────────────────────

    def _collect_refs(
        self,
        node: Node,
        ctx: ParseContext,
        local_types: dict[str, str],
    ) -> None:
        for child in node.children:
            if child.type == "class_definition":
                name = self._field(child, "name")
                class_id = f"{ctx.module_id}:{name}" if name else ctx.parent_id
                # Inherit refs
                supers = child.child_by_field_name("superclasses")
                if supers:
                    for arg in supers.children:
                        base = self._extract_base_name(arg)
                        if base:
                            self.schema.on_inherit(child, ctx, base)
                            ctx.inherit_refs_out.append({
                                "class_id": class_id,
                                "base_name": base,
                            })
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
                name = self._field(child, "name")
                func_id = f"{ctx.parent_id}:{name}" if name else ctx.parent_id
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
                self._collect_refs(child, ctx, local_types)

            elif child.type in ("assignment", "annotated_assignment", "expression_statement"):
                target_node = child
                if child.type == "expression_statement" and child.child_count > 0:
                    if child.children[0].type == "assignment":
                        target_node = child.children[0]

                if target_node.type == "assignment":
                    self._collect_local_assignment(target_node, ctx, local_types)
                elif target_node.type == "annotated_assignment":
                    self._collect_ann_assignment(target_node, local_types)

                self.schema.on_assignment(target_node, ctx)
                self._collect_refs(child, ctx, local_types)

            else:
                self._collect_refs(child, ctx, local_types)

    def _handle_call(
        self, call_node: Node, ctx: ParseContext, local_types: dict[str, str]
    ) -> None:
        ref = self._extract_call_ref(call_node, ctx.parent_id, ctx.current_class_id, local_types)
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
        func = call_node.child_by_field_name("function")
        if func is None:
            return None

        base = {"caller_id": caller_id, "line": call_node.start_point[0] + 1, "file": self.rel_path}

        if func.type == "identifier":
            name = self._text(func)
            if name in _BUILTINS:
                return None
            return {**base, "kind": "simple", "name": name}

        if func.type == "attribute":
            obj = func.child_by_field_name("object")
            attr = func.child_by_field_name("attribute")
            if obj is None or attr is None:
                return None
            attr_name = self._text(attr)
            if attr_name in _BUILTINS:
                return None
            obj_text = self._text(obj)

            if obj_text in ("self", "cls"):
                return {**base, "kind": "self_method", "name": attr_name, "class_id": current_class_id}

            if obj.type == "attribute":
                inner_obj = obj.child_by_field_name("object")
                inner_attr = obj.child_by_field_name("attribute")
                if inner_obj and inner_attr and self._text(inner_obj) in ("self", "cls"):
                    return {
                        **base,
                        "kind": "self_attr_method",
                        "name": attr_name,
                        "attr": self._text(inner_attr),
                        "class_id": current_class_id,
                    }

            if obj_text in local_types:
                return {**base, "kind": "local_method", "name": attr_name, "type_name": local_types[obj_text]}

            return {**base, "kind": "attr", "name": attr_name, "obj": obj_text}

        return None

    def _collect_local_assignment(
        self, node: Node, ctx: ParseContext, local_types: dict[str, str]
    ) -> None:
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or right.type != "call":
            return

        func = right.child_by_field_name("function")
        if func is None:
            return

        type_name = None
        if func.type == "identifier":
            type_name = self._text(func)
        elif func.type == "attribute":
            type_attr = func.child_by_field_name("attribute")
            type_name = self._text(type_attr) if type_attr else None

        if not type_name or type_name in _BUILTINS:
            return

        if left.type == "attribute" and ctx.current_class_id:
            obj_node = left.child_by_field_name("object")
            attr_node = left.child_by_field_name("attribute")
            if obj_node and attr_node and self._text(obj_node) in ("self", "cls"):
                ctx.instance_attr_types_out.append({
                    "class_id": ctx.current_class_id,
                    "attr": self._text(attr_node),
                    "type_name": type_name,
                })
        elif left.type == "identifier":
            local_types[self._text(left)] = type_name

    def _collect_ann_assignment(self, node: Node, local_types: dict[str, str]) -> None:
        target = node.child_by_field_name("target")
        type_node = node.child_by_field_name("type")
        if not target or not type_node:
            return
        type_name = self._extract_base_name(type_node)
        if not type_name:
            return
        if target.type == "identifier":
            local_types[self._text(target)] = type_name

    def _extract_params_types(self, func_node: Node, local_types: dict[str, str]) -> None:
        params = func_node.child_by_field_name("parameters")
        if not params:
            return
        for param in params.children:
            if param.type == "typed_parameter":
                name_node = param.child_by_field_name("name")
                type_node = param.child_by_field_name("type")
                if name_node and type_node:
                    local_types[self._text(name_node)] = self._extract_base_name(type_node)

    # ── scope building ────────────────────────────────────────────────────────

    def _build_scopes(
        self, nodes: list[dict]
    ) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        local_scope: dict[str, str] = {}
        class_scopes: dict[str, dict[str, str]] = {}

        for node in nodes:
            label = node["labels"][0]
            if label == "Module":
                continue
            node_id = node["id"]
            name = node["properties"].get("name", "")
            parts = node_id[len(self.module_id):].lstrip(":").split(":")

            if len(parts) == 1:
                local_scope[name] = node_id
            elif len(parts) == 2 and label in ("Function", "METHOD"):
                class_id = f"{self.module_id}:{parts[0]}"
                class_scopes.setdefault(class_id, {})[name] = node_id

        return local_scope, class_scopes

    # ── helpers ───────────────────────────────────────────────────────────────

    def _text(self, node: Node) -> str:
        return self._source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _field(self, node: Node, field: str) -> str:
        child = node.child_by_field_name(field)
        return self._text(child) if child else ""

    def _iter_all(self, node: Node):
        stack = [node]
        while stack:
            n = stack.pop()
            yield n
            stack.extend(reversed(n.children))

    def _extract_base_name(self, node: Node) -> str:
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

    # ── pass 3: cross-file resolution (static) ───────────────────────────────

    @staticmethod
    def resolve_cross_file(all_results: list[dict], schema: SchemaPlugin) -> list[dict]:
        # Single pass: build all indexes simultaneously
        all_node_ids: set[str] = set()
        all_class_scopes: dict[str, dict[str, str]] = {}
        instance_attr_map: dict[tuple, list[str]] = {}
        file_data: dict[str, dict] = {}

        # global_name_scope: name → [node_ids] across ALL files (module-level only)
        global_name_scope: dict[str, list[str]] = {}

        for r in all_results:
            file_data[r["module_id"]] = r
            for n in r["nodes"]:
                all_node_ids.add(n["id"])
            all_class_scopes.update(r.get("class_scopes", {}))
            for entry in r.get("instance_attr_types", []):
                key = (entry["class_id"], entry["attr"])
                instance_attr_map.setdefault(key, []).append(entry["type_name"])
            for name, nid in r.get("local_scope", {}).items():
                global_name_scope.setdefault(name, []).append(nid)

        # Build inheritance map after all_node_ids is complete
        inheritance_map: dict[str, list[str]] = {}
        for r in all_results:
            fmap = r.get("from_import_map", {})
            lscope = r.get("local_scope", {})
            for ref in r.get("inherit_refs", []):
                for base_id in ASTEngine._resolve_name(ref["base_name"], fmap, lscope, all_node_ids):
                    inheritance_map.setdefault(ref["class_id"], []).append(base_id)

        edges: list[dict] = []
        seen: set[tuple] = set()
        resolved = unresolved = 0
        total_refs = sum(len(r.get("call_refs", [])) for r in all_results)
        logger.info(f"Resolving {total_refs} refs...")

        for result in all_results:
            import_map = result.get("import_map", {})
            from_import_map = result.get("from_import_map", {})
            local_scope = result.get("local_scope", {})
            class_scopes = result.get("class_scopes", {})

            for ref in result.get("call_refs", []):
                caller_id = ref["caller_id"]
                targets = ASTEngine._resolve_call(
                    ref, import_map, from_import_map, local_scope, class_scopes,
                    file_data, all_node_ids, all_class_scopes, instance_attr_map, inheritance_map,
                    global_name_scope,
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
                            "type": schema.call_edge_type,
                            "source": caller_id,
                            "target": target_id,
                            "line": ref["line"],
                        })

            for ref in result.get("inherit_refs", []):
                class_id = ref["class_id"]
                base_name = ref["base_name"]
                fmap = result.get("from_import_map", {})
                lscope = result.get("local_scope", {})
                for target_id in ASTEngine._resolve_name(base_name, fmap, lscope, all_node_ids):
                    key = (class_id, target_id, schema.inherit_edge_type)
                    if class_id != target_id and key not in seen:
                        seen.add(key)
                        edges.append({"type": schema.inherit_edge_type, "source": class_id, "target": target_id})

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
        kind = ref["kind"]
        func_name = ref["name"]

        if kind == "simple":
            resolved = ASTEngine._resolve_name(func_name, from_import_map, local_scope, all_node_ids)
            if resolved:
                return resolved
            # Fallback: global unique-name search across all module-level definitions.
            # Only emit an edge when exactly one candidate exists project-wide (avoids
            # false positives for common names that appear in multiple files).
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
            candidates = [ref.get("class_id")]
        elif kind == "self_attr_method":
            class_id = ref.get("class_id")
            attr_name = ref.get("attr")
            if class_id and attr_name:
                type_names = ASTEngine._find_attr_type_recursive(
                    class_id, attr_name, instance_attr_map, inheritance_map, set()
                )
                for tn in type_names:
                    candidates.extend(ASTEngine._resolve_name(tn, from_import_map, local_scope, all_node_ids))
        elif kind == "local_method":
            type_name = ref.get("type_name")
            candidates = ASTEngine._resolve_name(type_name, from_import_map, local_scope, all_node_ids)
        elif kind == "attr":
            obj_name = ref["obj"]
            module_id = import_map.get(obj_name)
            if module_id and module_id in file_data:
                target = file_data[module_id]
                nid = target.get("local_scope", {}).get(func_name)
                if not nid:
                    predicted = target.get("from_import_map", {}).get(func_name)
                    if predicted and predicted in all_node_ids:
                        nid = predicted
                if nid:
                    return [nid]
            candidates = ASTEngine._resolve_name(obj_name, from_import_map, local_scope, all_node_ids)

        for start_class_id in candidates:
            if not start_class_id:
                continue
            nid = ASTEngine._find_method_recursive(
                start_class_id, func_name, all_class_scopes, inheritance_map, set()
            )
            if nid:
                return [nid]

        # 1-candidate-only fallback: resolve only when unambiguous
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
    def _resolve_name(name: str, from_import_map: dict, local_scope: dict, all_node_ids: set) -> list[str]:
        nid = local_scope.get(name)
        if nid and nid in all_node_ids:
            return [nid]
        predicted = from_import_map.get(name)
        if predicted and predicted in all_node_ids:
            return [predicted]
        return []

    @staticmethod
    def _find_method_recursive(
        class_id: str, method_name: str, all_class_scopes: dict, inheritance_map: dict, visited: set
    ) -> str | None:
        if class_id in visited:
            return None
        visited.add(class_id)
        nid = all_class_scopes.get(class_id, {}).get(method_name)
        if nid:
            return nid
        for base_id in inheritance_map.get(class_id, []):
            found = ASTEngine._find_method_recursive(base_id, method_name, all_class_scopes, inheritance_map, visited)
            if found:
                return found
        return None

    @staticmethod
    def _find_attr_type_recursive(
        class_id: str, attr_name: str, instance_attr_map: dict, inheritance_map: dict, visited: set
    ) -> list[str]:
        if class_id in visited:
            return []
        visited.add(class_id)
        types = instance_attr_map.get((class_id, attr_name), [])
        if types:
            return types
        for parent_id in inheritance_map.get(class_id, []):
            res = ASTEngine._find_attr_type_recursive(parent_id, attr_name, instance_attr_map, inheritance_map, visited)
            if res:
                return res
        return []
