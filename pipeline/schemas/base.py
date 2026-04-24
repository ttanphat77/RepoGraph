from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ParseContext:
    """Carries per-node state while the engine walks the AST.

    The engine creates one context per file and mutates parent_id / in_class /
    current_class_id as it descends into class and function bodies.  Schema
    plugins read these fields and call emit_node / emit_edge to produce output.
    """

    module_id: str
    parent_id: str
    in_class: bool
    is_module_scope: bool
    current_class_id: str | None

    # Accumulated output — the engine returns these after parsing
    nodes_out: list[dict] = field(default_factory=list)
    edges_out: list[dict] = field(default_factory=list)
    call_refs_out: list[dict] = field(default_factory=list)
    inherit_refs_out: list[dict] = field(default_factory=list)
    instance_attr_types_out: list[dict] = field(default_factory=list)

    # Injected by the engine so plugins don't need to import tree-sitter directly
    text_of: Callable = field(default=None, repr=False)

    def emit_node(self, label: str, nid: str, props: dict) -> None:
        self.nodes_out.append({"labels": [label], "id": nid, "properties": props})

    def emit_edge(self, etype: str, src: str, tgt: str, **extra) -> None:
        entry = {"type": etype, "source": src, "target": tgt}
        entry.update(extra)
        self.edges_out.append(entry)


class SchemaPlugin(ABC):
    """Interface every schema must implement.

    Each callback receives a tree-sitter Node and the current ParseContext.
    Return the node-id of the entity just emitted so the engine can use it
    as parent_id when recursing into the subtree, or None to keep parent_id
    unchanged.

    The engine guarantees callbacks are invoked only for the relevant
    tree-sitter node types.  Plugins do not need to recurse themselves.
    """

    @abstractmethod
    def on_class(self, node, ctx: ParseContext) -> str | None:
        """Called for every class_definition node."""

    @abstractmethod
    def on_function(self, node, ctx: ParseContext) -> str | None:
        """Called for function_definition and async_function_definition."""

    def on_assignment(self, node, ctx: ParseContext) -> None:
        """Called for assignment and annotated_assignment nodes."""

    def on_import(self, target_module_id: str, ctx: ParseContext) -> None:
        """Called when an import statement resolves to an internal repo module.
        Emit an import-style edge here if the schema needs one."""

    def on_call(self, node, ctx: ParseContext) -> None:
        """Called for call nodes — collect unresolved call refs."""

    def on_inherit(self, node, ctx: ParseContext, base_name: str) -> None:
        """Called once per base class name in a class definition."""

    # ── resolver contract ─────────────────────────────────────────────────────

    @property
    @abstractmethod
    def call_edge_type(self) -> str:
        """Edge type to emit when a call ref is resolved (e.g. 'Calls', 'USES')."""

    @property
    @abstractmethod
    def inherit_edge_type(self) -> str:
        """Edge type to emit when an inherit ref is resolved (e.g. 'Inherits', 'INHERITS')."""
