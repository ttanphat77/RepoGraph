# =============================================================================
# pipeline/schemas/simple.py — Schema "simple"
#
# Schema mặc định, tập trung vào cấu trúc file-level và luồng gọi hàm.
#
# Nodes : Module, Class, Function
# Edges : Defines (cấu trúc), Calls (gọi hàm), Imports (phụ thuộc),
#         Inherits (kế thừa)
#
# Cách đọc đồ thị:
#   Module --Defines--> Class --Defines--> Function
#   Module --Imports--> Module
#   Function --Calls--> Function
#   Class --Inherits--> Class
# =============================================================================

from __future__ import annotations

from pipeline.schemas.base import ParseContext, SchemaPlugin


class SimpleSchema(SchemaPlugin):
    """Schema đơn giản: Module/Class/Function với 4 loại cạnh."""

    # ── SchemaPlugin interface ────────────────────────────────────────────────

    @property
    def call_edge_type(self) -> str:
        # Engine dùng tên này khi tạo cạnh từ resolved call refs
        return "Calls"

    @property
    def inherit_edge_type(self) -> str:
        # Engine dùng tên này khi tạo cạnh từ resolved inherit refs
        return "Inherits"

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def on_class(self, node, ctx: ParseContext) -> str | None:
        """
        Emit node Class và cạnh Defines từ entity cha (module hoặc class lồng nhau).

        Node ID có dạng: "{module_id}:{ClassName}"
        Ví dụ: "abc123:django/db/models.py:QuerySet"
        """
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None  # class không tên (hiếm gặp) — bỏ qua

        cid = f"{ctx.module_id}:{name}"

        ctx.emit_node("Class", cid, {
            "name": name,
            # commit là phần đầu của module_id trước dấu ':'
            "commit":     ctx.module_id.split(":")[0],
            # file là phần còn lại (hỗ trợ path có dấu ':' trên Windows)
            "file":       ":".join(ctx.module_id.split(":")[1:]),
            "directory":  _directory(ctx.module_id),
            "start_line": node.start_point[0] + 1,  # tree-sitter dùng 0-index
            "end_line":   node.end_point[0] + 1,
            # Toàn bộ source code của class — dùng làm context cho LLM.
            # Giới hạn 8000 ký tự để tránh vượt giới hạn property Neo4j (64KB).
            "source":     ctx.text_of(node)[:8000],
        })

        # Cạnh Defines đi từ parent (module hoặc class cha) đến class này
        ctx.emit_edge("Defines", ctx.parent_id, cid)
        return cid  # engine dùng cid làm parent_id khi đi vào thân class

    def on_function(self, node, ctx: ParseContext) -> str | None:
        """
        Emit node Function và cạnh Defines từ entity cha.

        Schema simple không phân biệt method (trong class) vs function (module-level).
        Cả hai đều là node "Function". Xem schema detailed nếu cần phân biệt.

        Node ID có dạng: "{parent_id}:{func_name}"
        Với method: "{module_id}:{ClassName}:{method_name}"
        Với function: "{module_id}:{func_name}"
        """
        name = ctx.text_of(node.child_by_field_name("name"))
        if not name:
            return None

        fid = f"{ctx.parent_id}:{name}"

        ctx.emit_node("Function", fid, {
            "name":       name,
            "commit":     ctx.module_id.split(":")[0],
            "file":       ":".join(ctx.module_id.split(":")[1:]),
            "directory":  _directory(ctx.module_id),
            "start_line": node.start_point[0] + 1,
            "end_line":   node.end_point[0] + 1,
            # Source code của function/method — giới hạn 8000 ký tự
            "source":     ctx.text_of(node)[:8000],
        })

        ctx.emit_edge("Defines", ctx.parent_id, fid)
        return fid

    def on_import(self, target_module_id: str, ctx: ParseContext) -> None:
        """
        Emit cạnh Imports từ module hiện tại đến module được import.
        Chỉ emit khi target là module nội bộ repo (đã được resolve bởi engine).
        External imports (vd: import os, import django) bị bỏ qua.
        """
        ctx.emit_edge("Imports", ctx.module_id, target_module_id)

    # on_assignment, on_call, on_inherit: kế thừa no-op từ SchemaPlugin


# ── Helpers ───────────────────────────────────────────────────────────────────

def _directory(module_id: str) -> str:
    """
    Trích phần thư mục từ module_id dạng 'commit:path/to/file.py'.
    Ví dụ: 'abc123:django/db/models.py' → 'django/db'
    """
    import os
    # Bỏ phần commit (trước ':' đầu tiên), giữ lại path
    rel = ":".join(module_id.split(":")[1:])
    return os.path.dirname(rel) or "."  # "." nếu file nằm ở root
