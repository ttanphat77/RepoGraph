# =============================================================================
# pipeline/schemas/base.py — Abstract Base Classes cho Schema System
#
# Định nghĩa hai thành phần cốt lõi:
#   - ParseContext : trạng thái được truyền xuống khi engine duyệt AST
#   - SchemaPlugin : interface mà mọi schema cụ thể phải implement
#
# Thiết kế này tách biệt hoàn toàn logic "parse AST" (ast_engine.py)
# khỏi logic "định nghĩa label/edge type" (schema plugins).
# Thêm schema mới không cần đụng vào engine.
# =============================================================================

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ParseContext:
    """
    Trạng thái ngữ cảnh được truyền qua từng bước duyệt AST trong một file.

    Engine tạo một ParseContext gốc cho mỗi file, sau đó tạo context con
    khi đi vào thân class hoặc function (parent_id, in_class, current_class_id
    thay đổi tương ứng). Các list *_out được chia sẻ — tất cả context trong
    một file ghi vào cùng một bộ kết quả.
    """

    # ID của module đang parse — dùng làm prefix cho mọi node ID trong file.
    # Dạng: "{base_commit}:{rel_path}", ví dụ: "abc123:django/db/models.py"
    module_id: str

    # ID của entity cha trực tiếp trong cây định nghĩa.
    # Khi ở top-level: parent_id == module_id.
    # Khi trong class Foo: parent_id == "{module_id}:Foo".
    # Khi trong method bar của Foo: parent_id == "{module_id}:Foo:bar".
    parent_id: str

    # True nếu đang trong thân class (dùng để phân biệt method vs function).
    in_class: bool

    # True nếu đang ở scope module-level (dùng để phát hiện global variables).
    is_module_scope: bool

    # ID của class hiện tại, dùng để resolve self.method() calls.
    # None nếu không trong class nào.
    current_class_id: str | None

    # ── Output lists — chia sẻ qua toàn bộ context trong một file ────────────

    # Danh sách node sẽ được ghi vào Neo4j
    nodes_out: list[dict] = field(default_factory=list)

    # Cạnh "chắc chắn" (Defines, Imports) — biết endpoint ngay khi parse
    edges_out: list[dict] = field(default_factory=list)

    # Call references chưa resolve — sẽ được xử lý ở Pass 2 cross-file
    call_refs_out: list[dict] = field(default_factory=list)

    # Inheritance references chưa resolve — sẽ được xử lý ở Pass 2
    inherit_refs_out: list[dict] = field(default_factory=list)

    # Ghi nhận self.x = TypeName(...) để resolve self.x.method() sau này
    instance_attr_types_out: list[dict] = field(default_factory=list)

    # Hàm trích text từ tree-sitter Node — inject bởi engine,
    # giúp schema không cần import tree-sitter trực tiếp.
    text_of: Callable = field(default=None, repr=False)

    def emit_node(self, label: str, nid: str, props: dict) -> None:
        """Thêm một node vào output. label là nhãn Neo4j (vd: 'Class', 'Function')."""
        self.nodes_out.append({"labels": [label], "id": nid, "properties": props})

    def emit_edge(self, etype: str, src: str, tgt: str, **extra) -> None:
        """
        Thêm một cạnh vào output.
        extra: các thuộc tính bổ sung (vd: line=42 cho Calls edge).
        """
        entry = {"type": etype, "source": src, "target": tgt}
        entry.update(extra)
        self.edges_out.append(entry)


class SchemaPlugin(ABC):
    """
    Interface mà mọi schema đồ thị phải implement.

    Engine gọi các callback (on_class, on_function, ...) khi gặp node AST
    tương ứng. Schema quyết định:
      - Dùng label gì (vd: "Class" hay "CLASS")
      - Emit những thuộc tính nào vào node
      - Emit cạnh nào (vd: "Defines" hay "CONTAINS")

    Mỗi callback trả về node-id của entity vừa emit, để engine dùng làm
    parent_id khi đi vào subtree. Trả về None để giữ nguyên parent_id.
    """

    @abstractmethod
    def on_class(self, node, ctx: ParseContext) -> str | None:
        """
        Gọi khi gặp `class_definition` trong AST.
        Emit node Class + cạnh Defines từ parent.
        """

    @abstractmethod
    def on_function(self, node, ctx: ParseContext) -> str | None:
        """
        Gọi khi gặp `function_definition` hoặc `async_function_definition`.
        Emit node Function/Method + cạnh tương ứng.
        """

    def on_assignment(self, node, ctx: ParseContext) -> None:
        """
        Gọi khi gặp assignment hoặc annotated_assignment.
        Schema detailed dùng để phát hiện FIELD (self.x = ...) và GLOBAL_VARIABLE.
        Schema simple bỏ qua (no-op).
        """

    def on_import(self, target_module_id: str, ctx: ParseContext) -> None:
        """
        Gọi khi một import statement resolve được thành module nội bộ repo.
        Emit cạnh Imports từ module hiện tại đến target module.
        """

    def on_call(self, node, ctx: ParseContext) -> None:
        """
        Gọi khi phát hiện call site.
        Thường là no-op — call refs được engine thu thập riêng để resolve
        cross-file ở Pass 2. Schema có thể dùng để emit metadata nếu cần.
        """

    def on_inherit(self, node, ctx: ParseContext, base_name: str) -> None:
        """
        Gọi khi phát hiện class kế thừa (superclass).
        base_name là tên raw (chưa resolve). Resolve sẽ diễn ra ở Pass 2.
        """

    # ── Resolver contract ─────────────────────────────────────────────────────
    # Hai property này bắt buộc để engine biết dùng edge type nào
    # khi resolve cross-file call và inheritance refs.

    @property
    @abstractmethod
    def call_edge_type(self) -> str:
        """Edge type cho resolved call (vd: 'Calls' với simple, 'USES' với detailed)."""

    @property
    @abstractmethod
    def inherit_edge_type(self) -> str:
        """Edge type cho resolved inheritance (vd: 'Inherits' hay 'INHERITS')."""
