# =============================================================================
# pipeline/schemas/detailed.py — Schema "detailed"
#
# Schema chi tiết hơn, phân biệt rõ từng loại thực thể trong code.
#
# Nodes : MODULE, CLASS, METHOD, FUNCTION, FIELD, GLOBAL_VARIABLE
# Edges : CONTAINS (bao hàm), INHERITS (kế thừa), HAS_METHOD (class→method),
#         HAS_FIELD (class→field), USES (gọi hàm — cross-file resolved)
#
# Điểm khác biệt so với schema simple:
#   - Phân biệt METHOD (trong class) vs FUNCTION (module-level)
#   - Theo dõi FIELD (self.x = ...) và GLOBAL_VARIABLE (x = ... ở module scope)
#   - Dùng "CONTAINS" thay "Defines" làm cạnh bao hàm chính
#   - Dùng "USES" thay "Calls" cho resolved calls
# =============================================================================

from __future__ import annotations

import os

from tree_sitter import Node

from pipeline.schemas.base import ParseContext, SchemaPlugin


class DetailedSchema(SchemaPlugin):
    """Schema đầy đủ: phân biệt method/function, theo dõi field và global var."""

    # ── SchemaPlugin interface ────────────────────────────────────────────────

    @property
    def call_edge_type(self) -> str:
        return "USES"

    @property
    def inherit_edge_type(self) -> str:
        return "INHERITS"

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def on_class(self, node: Node, ctx: ParseContext) -> str | None:
        """
        Emit node CLASS và cạnh CONTAINS từ parent module/class.
        Label viết hoa để phân biệt với schema simple (label 'Class').
        """
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None

        cid = f"{ctx.module_id}:{name}"
        ctx.emit_node("CLASS", cid, {
            "name": name,
            **_common_props(ctx, node),  # commit, file, directory, start/end_line, source
        })
        ctx.emit_edge("CONTAINS", ctx.parent_id, cid)
        return cid

    def on_function(self, node: Node, ctx: ParseContext) -> str | None:
        """
        Emit node METHOD (khi trong class) hoặc FUNCTION (khi ở module level).

        Đây là điểm phân biệt chính với schema simple:
          - METHOD: hàm định nghĩa trong thân class, kể cả staticmethod và classmethod
          - FUNCTION: hàm ở module scope (top-level)

        Cạnh tương ứng:
          - HAS_METHOD: class → method (semantic rõ hơn "Defines")
          - CONTAINS:   module → function
        """
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None

        nid = f"{ctx.parent_id}:{name}"

        if ctx.in_class:
            # Method — nằm trong class
            ctx.emit_node("METHOD", nid, {
                "name": name,
                **_common_props(ctx, node),
            })
            ctx.emit_edge("HAS_METHOD", ctx.parent_id, nid)
        else:
            # Function — module level
            ctx.emit_node("FUNCTION", nid, {
                "name": name,
                **_common_props(ctx, node),
            })
            ctx.emit_edge("CONTAINS", ctx.parent_id, nid)

        return nid

    def on_assignment(self, node: Node, ctx: ParseContext) -> None:
        """
        Phát hiện và emit FIELD hoặc GLOBAL_VARIABLE từ assignment nodes.

        FIELD: `self.x = ...` hoặc `cls.x = ...` trong thân class
               → node FIELD + cạnh HAS_FIELD từ class
        GLOBAL_VARIABLE: `x = ...` ở module scope (is_module_scope=True)
               → node GLOBAL_VARIABLE + cạnh CONTAINS từ module

        Lưu ý: assignment trong function body bị bỏ qua (local variable).
        """
        # Lấy phía trái của assignment (target)
        left = node.child_by_field_name("left") or node.child_by_field_name("target")
        if left is None:
            return

        # Trường hợp 1: self.x = ... hoặc cls.x = ... (trong class)
        if ctx.in_class and ctx.current_class_id and left.type == "attribute":
            obj  = left.child_by_field_name("object")
            attr = left.child_by_field_name("attribute")
            if obj and attr and ctx.text_of(obj) in ("self", "cls"):
                attr_name = ctx.text_of(attr)
                fid = f"{ctx.current_class_id}:{attr_name}"
                ctx.emit_node("FIELD", fid, {
                    "name":   attr_name,
                    "commit": _commit(ctx),
                    "file":   _file(ctx),
                })
                ctx.emit_edge("HAS_FIELD", ctx.current_class_id, fid)

        # Trường hợp 2: x = ... ở module scope
        elif ctx.is_module_scope and left.type == "identifier":
            var_name = ctx.text_of(left)
            vid = f"{ctx.module_id}:{var_name}"
            ctx.emit_node("GLOBAL_VARIABLE", vid, {
                "name":   var_name,
                "commit": _commit(ctx),
                "file":   _file(ctx),
            })
            ctx.emit_edge("CONTAINS", ctx.module_id, vid)

    def on_import(self, target_module_id: str, ctx: ParseContext) -> None:
        """Emit cạnh IMPORTS từ module hiện tại đến module được import."""
        ctx.emit_edge("IMPORTS", ctx.module_id, target_module_id)

    def on_call(self, node: Node, ctx: ParseContext) -> None:
        # Call refs được engine thu thập riêng và resolve ở Pass 2.
        # USES edges được tạo trong ASTEngine.resolve_cross_file, không ở đây.
        pass

    def on_inherit(self, node: Node, ctx: ParseContext, base_name: str) -> None:
        # Inherit refs được engine thu thập riêng và resolve ở Pass 2.
        # INHERITS edges được tạo trong ASTEngine.resolve_cross_file.
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _commit(ctx: ParseContext) -> str:
    """Trích phần commit hash từ module_id dạng 'commit:path'."""
    return ctx.module_id.split(":")[0]


def _file(ctx: ParseContext) -> str:
    """Trích phần file path từ module_id (hỗ trợ path có dấu ':' trên Windows)."""
    return ":".join(ctx.module_id.split(":")[1:])


def _common_props(ctx: ParseContext, node: Node) -> dict:
    """
    Tập thuộc tính chung cho mọi node trong schema detailed.

    source bị giới hạn 8000 ký tự để tránh vượt giới hạn Neo4j property (64KB).
    Source code này được dùng làm context trong bước RAG Generation.
    """
    rel = _file(ctx)
    return {
        "commit":     _commit(ctx),
        "file":       rel,
        "directory":  os.path.dirname(rel) or ".",
        "start_line": node.start_point[0] + 1,  # tree-sitter dùng 0-index
        "end_line":   node.end_point[0] + 1,
        # Raw source code của node — key cho RAG context building
        "source":     ctx.text_of(node)[:8000],
    }
