"""
Schema "simple" — reproduces the original graph schema.

Nodes : Module, Class, Function
Edges : Defines, Calls, Imports, Inherits
"""

from __future__ import annotations

from pipeline.schemas.base import ParseContext, SchemaPlugin


class SimpleSchema(SchemaPlugin):

    # ── SchemaPlugin interface ────────────────────────────────────────────────

    @property
    def call_edge_type(self) -> str:
        return "Calls"

    @property
    def inherit_edge_type(self) -> str:
        return "Inherits"

    # ── callbacks ─────────────────────────────────────────────────────────────

    def on_class(self, node, ctx: ParseContext) -> str | None:
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None
        cid = f"{ctx.module_id}:{name}"
        ctx.emit_node("Class", cid, {
            "name": name,
            "commit": ctx.module_id.split(":")[0],
            "file": ":".join(ctx.module_id.split(":")[1:]),
            "directory": _directory(ctx.module_id),
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
        })
        ctx.emit_edge("Defines", ctx.parent_id, cid)
        return cid

    def on_function(self, node, ctx: ParseContext) -> str | None:
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None
        fid = f"{ctx.parent_id}:{name}"
        ctx.emit_node("Function", fid, {
            "name": name,
            "commit": ctx.module_id.split(":")[0],
            "file": ":".join(ctx.module_id.split(":")[1:]),
            "directory": _directory(ctx.module_id),
            "start_line": node.start_point[0] + 1,
            "end_line": node.end_point[0] + 1,
        })
        ctx.emit_edge("Defines", ctx.parent_id, fid)
        return fid

    def on_import(self, target_module_id: str, ctx: ParseContext) -> None:
        ctx.emit_edge("Imports", ctx.module_id, target_module_id)

    # on_assignment, on_call, on_inherit: use base no-ops


# ── helpers ───────────────────────────────────────────────────────────────────

def _directory(module_id: str) -> str:
    """Extract the directory part from a module_id like 'commit:path/to/file.py'."""
    import os
    rel = ":".join(module_id.split(":")[1:])
    return os.path.dirname(rel) or "."
