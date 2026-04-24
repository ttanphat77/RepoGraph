"""
Schema "detailed" — richer graph schema with method/field/variable distinction.

Nodes : MODULE, CLASS, METHOD, FUNCTION, FIELD, GLOBAL_VARIABLE
Edges : CONTAINS, INHERITS, HAS_METHOD, HAS_FIELD, USES
"""

from __future__ import annotations

import os

from tree_sitter import Node

from pipeline.schemas.base import ParseContext, SchemaPlugin


class DetailedSchema(SchemaPlugin):

    # ── SchemaPlugin interface ────────────────────────────────────────────────

    @property
    def call_edge_type(self) -> str:
        return "USES"

    @property
    def inherit_edge_type(self) -> str:
        return "INHERITS"

    # ── callbacks ─────────────────────────────────────────────────────────────

    def on_class(self, node: Node, ctx: ParseContext) -> str | None:
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None
        cid = f"{ctx.module_id}:{name}"
        ctx.emit_node("CLASS", cid, {
            "name": name,
            **_common_props(ctx, node),
        })
        ctx.emit_edge("CONTAINS", ctx.parent_id, cid)
        return cid

    def on_function(self, node: Node, ctx: ParseContext) -> str | None:
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None
        nid = f"{ctx.parent_id}:{name}"

        if ctx.in_class:
            ctx.emit_node("METHOD", nid, {
                "name": name,
                **_common_props(ctx, node),
            })
            ctx.emit_edge("HAS_METHOD", ctx.parent_id, nid)
        else:
            ctx.emit_node("FUNCTION", nid, {
                "name": name,
                **_common_props(ctx, node),
            })
            ctx.emit_edge("CONTAINS", ctx.parent_id, nid)

        return nid

    def on_assignment(self, node: Node, ctx: ParseContext) -> None:
        """Emit FIELD (self.x = ...) or GLOBAL_VARIABLE (x = ... at module scope)."""
        left = node.child_by_field_name("left") or node.child_by_field_name("target")
        if left is None:
            return

        if ctx.in_class and ctx.current_class_id and left.type == "attribute":
            obj = left.child_by_field_name("object")
            attr = left.child_by_field_name("attribute")
            if obj and attr and ctx.text_of(obj) in ("self", "cls"):
                attr_name = ctx.text_of(attr)
                fid = f"{ctx.current_class_id}:{attr_name}"
                ctx.emit_node("FIELD", fid, {
                    "name": attr_name,
                    "commit": _commit(ctx),
                    "file": _file(ctx),
                })
                ctx.emit_edge("HAS_FIELD", ctx.current_class_id, fid)

        elif ctx.is_module_scope and left.type == "identifier":
            var_name = ctx.text_of(left)
            vid = f"{ctx.module_id}:{var_name}"
            ctx.emit_node("GLOBAL_VARIABLE", vid, {
                "name": var_name,
                "commit": _commit(ctx),
                "file": _file(ctx),
            })
            ctx.emit_edge("CONTAINS", ctx.module_id, vid)

    def on_call(self, node: Node, ctx: ParseContext) -> None:
        pass  # call_refs are collected by the engine; USES edges created in resolve_cross_file

    def on_inherit(self, node: Node, ctx: ParseContext, base_name: str) -> None:
        pass  # inherit_refs collected by engine; INHERITS edges created in resolve_cross_file


# ── helpers ───────────────────────────────────────────────────────────────────

def _commit(ctx: ParseContext) -> str:
    return ctx.module_id.split(":")[0]


def _file(ctx: ParseContext) -> str:
    return ":".join(ctx.module_id.split(":")[1:])


def _common_props(ctx: ParseContext, node: Node) -> dict:
    rel = _file(ctx)
    return {
        "commit": _commit(ctx),
        "file": rel,
        "directory": os.path.dirname(rel) or ".",
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
    }
