"""
Parse Python files with tree-sitter.

Three-pass design (per-file then cross-file)
────────────────────────────────────────────
Pass 1a (per-file): collect Def nodes (Module/Class/Function) + Defines/Imports edges,
                    import bindings (import_map, from_import_map), local scope.
Pass 1b (per-file): collect Ref data — call sites (call_refs) and inheritance
                    references (inherit_refs). No edge building, only data collection.
Pass 2  (cross-file): resolve Refs → Def nodes using import-aware, scope-bounded
                      resolution. Never falls back to global name matching.

Resolution strategy (in priority order):
  simple call foo()       → local scope → explicit from-import
  self.method()           → same class methods only
  self.x.method()         → type of self.x inferred from self.x = TypeName(...) assignments
  module.func()           → module must be a known import; func must exist in it
  ClassName.method()      → class must be local or from-imported; method must exist in it
  everything else         → dropped (no false positives)
"""

from __future__ import annotations

import logging
import os
from tree_sitter import Language, Parser, Node
import tree_sitter_python as tspython

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


class ASTParser:
    def __init__(self, file_path: str, repo_path: str, base_commit: str):
        self.file_path = file_path
        self.repo_path = repo_path
        self.base_commit = base_commit

        try:
            self.rel_path = os.path.relpath(file_path, repo_path).replace("\\", "/")
        except ValueError:
            self.rel_path = file_path.replace("\\", "/")

        self.module_id  = f"{self.base_commit}:{self.rel_path}"
        self._directory = os.path.dirname(self.rel_path) or "."

        self.nodes: list[dict] = []
        self.definite_edges: list[dict] = []

        # Pass 1b — Ref collection results
        # call_refs:    [{caller_id, kind, name, line, file, ...kind-specific fields}]
        # inherit_refs: [{class_id, base_name}]
        self.call_refs: list[dict] = []
        self.inherit_refs: list[dict] = []
        # {class_id, attr, type_name} — self.x = TypeName(...) assignments
        self.instance_attr_types: list[dict] = []

        # import X [as Y]          → import_map[Y] = module_id
        # import X.Y               → import_map["X"] = module_id, import_map["X.Y"] = module_id
        self.import_map: dict[str, str] = {}

        # from X import Y [as Z]   → from_import_map[Z] = predicted_node_id | None
        # None means the source module is external (not in repo)
        self.from_import_map: dict[str, str | None] = {}

        self._source: bytes = b""

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

        self.nodes.append({
            "labels": ["Module"],
            "id": self.module_id,
            "properties": {"name": self.rel_path, "commit": self.base_commit},
        })

        # Pass 1a — collect Def nodes (Module/Class/Function) + Defines/Imports edges
        self._walk_definitions(tree.root_node, parent_id=self.module_id)
        self._walk_imports(tree.root_node)
        local_scope, class_scopes = self._build_scopes()

        # Pass 1b — collect Ref data: call sites + inheritance references
        # Now tracking local variable types (from hints and assignments)
        self._collect_refs(tree.root_node, context_id=self.module_id, current_class_id=None, local_types={})

        return {
            "module_id": self.module_id,
            "nodes": self.nodes,
            "definite_edges": self.definite_edges,
            "call_refs": self.call_refs,
            "inherit_refs": self.inherit_refs,
            "instance_attr_types": self.instance_attr_types,
            "import_map": self.import_map,
            "from_import_map": self.from_import_map,
            "local_scope": local_scope,
            "class_scopes": class_scopes,
        }

    # ── pass 1: definitions ───────────────────────────────────────────────────

    def _walk_definitions(self, node: Node, parent_id: str) -> None:
        for child in node.children:
            if child.type == "class_definition" and "Class" in config.ENABLED_NODES:
                name = self._field(child, "name")
                if not name:
                    continue
                class_id = f"{self.module_id}:{name}"
                self.nodes.append({
                    "labels": ["Class"],
                    "id": class_id,
                    "properties": {
                        "name": name,
                        "commit": self.base_commit,
                        "file": self.rel_path,
                        "directory": self._directory,
                        "start_line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                    },
                })
                self.definite_edges.append({"type": "Defines", "source": parent_id, "target": class_id})
                self._walk_definitions(child, parent_id=class_id)

            elif child.type in ("function_definition", "async_function_definition") and "Function" in config.ENABLED_NODES:
                name = self._field(child, "name")
                if not name:
                    continue
                func_id = f"{parent_id}:{name}"
                self.nodes.append({
                    "labels": ["Function"],
                    "id": func_id,
                    "properties": {
                        "name": name,
                        "commit": self.base_commit,
                        "file": self.rel_path,
                        "directory": self._directory,
                        "start_line": child.start_point[0] + 1,
                        "end_line": child.end_point[0] + 1,
                    },
                })
                self.definite_edges.append({"type": "Defines", "source": parent_id, "target": func_id})
                self._walk_definitions(child, parent_id=func_id)

            else:
                self._walk_definitions(child, parent_id)

    # ── pass 1: imports ───────────────────────────────────────────────────────

    def _walk_imports(self, node: Node) -> None:
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
                            self._add_import_edge(tid)
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
                    self._add_import_edge(module_tid)

                for local_name, orig_name in self._get_from_imports(child):
                    # Check if imported name is itself a submodule
                    sub_tid = self._resolve_module(f"{mod_str}.{orig_name}")
                    if sub_tid:
                        self.import_map[local_name] = sub_tid
                    elif module_tid:
                        # Predicted node id: "{module_tid}:{orig_name}"
                        self.from_import_map[local_name] = f"{module_tid}:{orig_name}"
                    else:
                        self.from_import_map[local_name] = None  # external

    def _add_import_edge(self, target_id: str) -> None:
        self.definite_edges.append({"type": "Imports", "source": self.module_id, "target": target_id})

    def _get_from_imports(self, from_stmt: Node) -> list[tuple[str, str]]:
        """Return [(local_name, original_name)] from an import_from_statement."""
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
            # Relative import
            dots     = len(module) - len(module.lstrip("."))
            rel_part = module.lstrip(".")
            base_dir = os.path.dirname(self.rel_path)
            for _ in range(dots - 1):
                base_dir = os.path.dirname(base_dir)
            parts = os.path.join(base_dir, rel_part.replace(".", os.sep)).replace("\\", "/") \
                    if rel_part else base_dir
        else:
            parts = module.replace(".", "/")

        for candidate in (f"{parts}.py", f"{parts}/__init__.py"):
            full = os.path.join(self.repo_path, candidate)
            if os.path.exists(full):
                rel = os.path.relpath(full, self.repo_path).replace("\\", "/")
                return f"{self.base_commit}:{rel}"
        return None

    # ── pass 1b: ref collection ───────────────────────────────────────────────

    def _collect_refs(self, node: Node, context_id: str, current_class_id: str | None, local_types: dict[str, str]) -> None:
        """
        Walk the AST and collect Ref data.
        Tracks local_types: {variable_name -> type_name} for the current function scope.
        """
        for child in node.children:
            if child.type == "class_definition":
                name = self._field(child, "name")
                class_id = f"{self.module_id}:{name}" if name else context_id
                supers = child.child_by_field_name("superclasses")
                if supers:
                    for arg in supers.children:
                        base = self._extract_base_name(arg)
                        if base:
                            self.inherit_refs.append({"class_id": class_id, "base_name": base})
                # Classes don't share local_types with external context normally
                self._collect_refs(child, context_id=class_id, current_class_id=class_id, local_types={})

            elif child.type in ("function_definition", "async_function_definition"):
                name = self._field(child, "name")
                func_id = f"{context_id}:{name}" if name else context_id
                # New scope for function
                func_locals = local_types.copy()
                self._extract_params_types(child, func_locals)
                self._collect_refs(child, context_id=func_id, current_class_id=current_class_id, local_types=func_locals)

            elif child.type == "call":
                ref = self._extract_call_ref(child, context_id, current_class_id, local_types)
                if ref is not None:
                    self.call_refs.append(ref)
                self._collect_refs(child, context_id=context_id, current_class_id=current_class_id, local_types=local_types)

            elif child.type in ("assignment", "annotated_assignment", "expression_statement"):
                # expression_statement might contain an assignment node as child in some tree-sitter versions
                target_node = child
                if child.type == "expression_statement" and child.child_count > 0:
                    if child.children[0].type == "assignment":
                        target_node = child.children[0]
                
                if target_node.type == "assignment":
                    self._collect_local_assignment(target_node, current_class_id, local_types)
                elif target_node.type == "annotated_assignment":
                    self._collect_ann_assignment(target_node, local_types)
                
                self._collect_refs(child, context_id=context_id, current_class_id=current_class_id, local_types=local_types)

            else:
                self._collect_refs(child, context_id=context_id, current_class_id=current_class_id, local_types=local_types)

    def _extract_params_types(self, func_node: Node, local_types: dict[str, str]) -> None:
        params = func_node.child_by_field_name("parameters")
        if not params:
            return
        for param in params.children:
            # typed_parameter: (identifier) : (type)
            if param.type == "typed_parameter":
                name_node = param.child_by_field_name("name")
                type_node = param.child_by_field_name("type")
                if name_node and type_node:
                    local_types[self._text(name_node)] = self._extract_base_name(type_node)
            elif param.type == "default_parameter":
                # Maybe handle default values too, but hints are more reliable
                name_node = param.child_by_field_name("name")
                if name_node and name_node.type == "typed_parameter":
                     type_node = name_node.child_by_field_name("type")
                     id_node = name_node.child_by_field_name("name")
                     if id_node and type_node:
                         local_types[self._text(id_node)] = self._extract_base_name(type_node)

    def _collect_ann_assignment(self, node: Node, local_types: dict[str, str]) -> None:
        # x: MyClass = ... or self.x: MyClass = ...
        target = node.child_by_field_name("target")
        type_node = node.child_by_field_name("type")
        if not target or not type_node:
            return
            
        type_name = self._extract_base_name(type_node)
        if not type_name:
            return

        if target.type == "identifier":
            local_types[self._text(target)] = type_name
        elif target.type == "attribute":
            # self.x: MyClass = ...
            obj_node = target.child_by_field_name("object")
            attr_node = target.child_by_field_name("attribute")
            if obj_node and attr_node and self._text(obj_node) in ("self", "cls"):
                # We need class context
                # This is tricky because we don't have current_class_id as param here
                # but we can infer it or just store it generally for now
                pass # Handled better in _collect_refs pass if we pass class_id

    def _collect_local_assignment(self, node: Node, current_class_id: str | None, local_types: dict[str, str]) -> None:
        """Record x = TypeName(...) or self.x = TypeName(...)"""
        left  = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left is None or right is None or right.type != "call":
            return
        
        # Determine the type being assigned
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

        # self.x = Type(...)
        if left.type == "attribute" and current_class_id:
            obj_node  = left.child_by_field_name("object")
            attr_node = left.child_by_field_name("attribute")
            if obj_node and attr_node and self._text(obj_node) in ("self", "cls"):
                self.instance_attr_types.append({
                    "class_id": current_class_id,
                    "attr": self._text(attr_node),
                    "type_name": type_name,
                })
        
        # x = Type(...)
        elif left.type == "identifier":
            local_types[self._text(left)] = type_name

    def _extract_call_ref(
        self, call_node: Node, caller_id: str, current_class_id: str | None, local_types: dict[str, str]
    ) -> dict | None:
        func = call_node.child_by_field_name("function")
        if func is None:
            return None

        base = {
            "caller_id": caller_id,
            "line": call_node.start_point[0] + 1,
            "file": self.rel_path,
        }

        if func.type == "identifier":
            name = self._text(func)
            if name in _BUILTINS:
                return None
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
                return {**base, "kind": "self_method", "name": attr_name, "class_id": current_class_id}
            
            # self.x.method()
            if obj.type == "attribute":
                inner_obj  = obj.child_by_field_name("object")
                inner_attr = obj.child_by_field_name("attribute")
                if inner_obj is not None and inner_attr is not None:
                    if self._text(inner_obj) in ("self", "cls"):
                        return {
                            **base,
                            "kind": "self_attr_method",
                            "name": attr_name,
                            "attr": self._text(inner_attr),
                            "class_id": current_class_id,
                        }
            
            # local_var.method()
            if obj_text in local_types:
                return {**base, "kind": "local_method", "name": attr_name, "type_name": local_types[obj_text]}

            return {**base, "kind": "attr", "name": attr_name, "obj": obj_text}

        return None

    def _extract_base_name(self, node: Node) -> str:
        if node.type == "identifier":
            return self._text(node)
        if node.type == "attribute":
            attr = node.child_by_field_name("attribute")
            return self._text(attr) if attr else ""
        if node.type == "subscript":
            val = node.child_by_field_name("value")
            return self._extract_base_name(val) if val else ""
        if node.type == "type": # in some versions
            return self._extract_base_name(node.children[0]) if node.child_count > 0 else ""
        return ""

    # ── scope building ────────────────────────────────────────────────────────

    def _build_scopes(self) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        local_scope: dict[str, str] = {}
        class_scopes: dict[str, dict[str, str]] = {}

        for node in self.nodes:
            label = node["labels"][0]
            if label == "Module":
                continue
            node_id = node["id"]
            name = node["properties"].get("name", "")
            parts = node_id[len(self.module_id):].lstrip(":").split(":")

            if len(parts) == 1:
                local_scope[name] = node_id
            elif len(parts) == 2 and label == "Function":
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

    # ── pass 2: cross-file resolution ─────────────────────────────────────────

    @staticmethod
    def resolve_cross_file(all_results: list[dict]) -> list[dict]:
        # Single pass: build all indexes simultaneously
        all_node_ids: set[str] = set()
        all_class_scopes: dict[str, dict[str, str]] = {}
        instance_attr_map: dict[tuple, list[str]] = {}
        file_data: dict[str, dict] = {}

        for r in all_results:
            file_data[r["module_id"]] = r
            for n in r["nodes"]:
                all_node_ids.add(n["id"])
            all_class_scopes.update(r.get("class_scopes", {}))
            for entry in r.get("instance_attr_types", []):
                key = (entry["class_id"], entry["attr"])
                instance_attr_map.setdefault(key, []).append(entry["type_name"])

        # Build inheritance map after all_node_ids is complete
        inheritance_map: dict[str, list[str]] = {}
        for r in all_results:
            from_import_map = r.get("from_import_map", {})
            local_scope = r.get("local_scope", {})
            for ref in r.get("inherit_refs", []):
                child_id = ref["class_id"]
                base_name = ref["base_name"]
                for base_id in ASTParser._resolve_name(base_name, from_import_map, local_scope, all_node_ids):
                    inheritance_map.setdefault(child_id, []).append(base_id)

        edges: list[dict] = []
        seen: set[tuple] = set()

        total_refs = sum(len(r.get("call_refs", [])) for r in all_results)
        logger.info(f"Resolving {total_refs} refs with inheritance awareness...")

        resolved = unresolved = 0

        for result in all_results:
            import_map      = result.get("import_map", {})
            from_import_map = result.get("from_import_map", {})
            local_scope     = result.get("local_scope", {})
            class_scopes    = result.get("class_scopes", {})

            for ref in result.get("call_refs", []):
                caller_id = ref["caller_id"]
                targets = ASTParser._resolve_call_advanced(
                    ref, import_map, from_import_map,
                    local_scope, class_scopes, file_data, all_node_ids, all_class_scopes,
                    instance_attr_map, inheritance_map
                )
                
                if targets:
                    resolved += 1
                else:
                    unresolved += 1
                    
                for target_id in targets:
                    key = (caller_id, target_id, "Calls")
                    if caller_id != target_id and key not in seen:
                        seen.add(key)
                        edges.append({
                            "type": "Calls",
                            "source": caller_id,
                            "target": target_id,
                            "line": ref["line"],
                        })

            for ref in result.get("inherit_refs", []):
                class_id  = ref["class_id"]
                base_name = ref["base_name"]
                for target_id in ASTParser._resolve_name(
                    base_name, from_import_map, local_scope, all_node_ids,
                ):
                    key = (class_id, target_id, "Inherits")
                    if class_id != target_id and key not in seen:
                        seen.add(key)
                        edges.append({"type": "Inherits", "source": class_id, "target": target_id})

        logger.info(f"Resolved: {resolved}, Unresolved: {unresolved}")
        return edges

    @staticmethod
    def _resolve_call_advanced(
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
    ) -> list[str]:
        kind = ref["kind"]
        func_name = ref["name"]

        # 1. Resolve potential Class ID candidates
        candidates = []
        if kind == "simple":
            return ASTParser._resolve_name(ref["name"], from_import_map, local_scope, all_node_ids)

        if kind == "self_method":
            candidates = [ref.get("class_id")]
        elif kind == "self_attr_method":
            class_id  = ref.get("class_id")
            attr_name = ref.get("attr")
            if class_id and attr_name:
                # Seek type in this class or parent classes
                type_names = ASTParser._find_attr_type_recursive(class_id, attr_name, instance_attr_map, inheritance_map, set())
                for tn in type_names:
                    candidates.extend(ASTParser._resolve_name(tn, from_import_map, local_scope, all_node_ids))
        elif kind == "local_method":
            type_name = ref.get("type_name")
            candidates = ASTParser._resolve_name(type_name, from_import_map, local_scope, all_node_ids)
        elif kind == "attr":
            obj_name  = ref["obj"]
            # Module call
            module_id = import_map.get(obj_name)
            if module_id and module_id in file_data:
                target = file_data[module_id]
                nid = target.get("local_scope", {}).get(func_name)
                if not nid:
                    predicted = target.get("from_import_map", {}).get(func_name)
                    if predicted and predicted in all_node_ids:
                        nid = predicted
                if nid: return [nid]
            candidates = ASTParser._resolve_name(obj_name, from_import_map, local_scope, all_node_ids)

        # 2. Look for the method in candidate classes + their inheritance chain
        for start_class_id in candidates:
            if not start_class_id: continue
            nid = ASTParser._find_method_recursive(start_class_id, func_name, all_class_scopes, inheritance_map, set())
            if nid: return [nid]
            
        return []

    @staticmethod
    def _find_attr_type_recursive(class_id: str, attr_name: str, instance_attr_map: dict, inheritance_map: dict, visited: set) -> list[str]:
        if class_id in visited: return []
        visited.add(class_id)
        
        types = instance_attr_map.get((class_id, attr_name), [])
        if types: return types
        
        for parent_id in inheritance_map.get(class_id, []):
            res = ASTParser._find_attr_type_recursive(parent_id, attr_name, instance_attr_map, inheritance_map, visited)
            if res: return res
        return []

    @staticmethod
    def _find_method_recursive(class_id: str, method_name: str, all_class_scopes: dict, inheritance_map: dict, visited: set) -> str | None:
        if class_id in visited: return None
        visited.add(class_id)
        
        nid = all_class_scopes.get(class_id, {}).get(method_name)
        if nid: return nid
        
        for base_id in inheritance_map.get(class_id, []):
            found = ASTParser._find_method_recursive(base_id, method_name, all_class_scopes, inheritance_map, visited)
            if found: return found
        
        return None

    @staticmethod
    def _resolve_name(
        name: str,
        from_import_map: dict,
        local_scope: dict,
        all_node_ids: set,
    ) -> list[str]:
        nid = local_scope.get(name)
        if nid and nid in all_node_ids:
            return [nid]
        predicted = from_import_map.get(name)
        if predicted and predicted in all_node_ids:
            return [predicted]
        return []
