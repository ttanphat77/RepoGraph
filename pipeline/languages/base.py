"""
pipeline/languages/base.py — LanguageExtractor interface.

Mỗi ngôn ngữ implement một instance của dataclass này, cung cấp
toàn bộ thông tin language-specific để ASTEngine không cần hardcode
bất kỳ node type hay field name nào.
"""

from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Parser


@dataclass(frozen=True)
class LanguageExtractor:
    # ── Parser ────────────────────────────────────────────────────────────────
    parser: Parser

    # ── Built-in names to skip when building call refs ────────────────────────
    builtins: frozenset

    # ── Definition node types ─────────────────────────────────────────────────
    function_types: tuple[str, ...]   # e.g. ("function_definition", "async_function_definition")
    class_types:    tuple[str, ...]   # e.g. ("class_definition",)

    # ── Other node types ──────────────────────────────────────────────────────
    call_type:        str             # "call" / "call_expression"
    import_type:      str             # "import_statement" / "import_declaration"
    from_import_type: str             # "import_from_statement" / "" if not supported
    assignment_types: tuple[str, ...] # ("assignment", "annotated_assignment", ...)

    # ── Import sub-node types ─────────────────────────────────────────────────
    import_name_types:    tuple[str, ...]  # node types inside import statement
    aliased_import_type:  str              # "aliased_import" / ""
    import_as_names_type: str              # "import_as_names" / ""
    wildcard_import_type: str              # "wildcard_import" / ""
    import_keyword_type:  str              # "import"
    identifier_type:      str              # "identifier" / "simple_identifier"

    # ── Field names — definition nodes ───────────────────────────────────────
    name_field:         str   # "name"
    params_field:       str   # "parameters" / "" if not a single named field
    superclasses_field: str   # "superclasses" / "" if not a named field
    module_name_field:  str   # "module_name" / "" if not a named field
    alias_name_field:   str   # original name inside aliased_import
    alias_alias_field:  str   # "as" alias inside aliased_import

    # ── Call expression structure ─────────────────────────────────────────────
    # Python:  call.child_by_field_name("function") → identifier | attribute
    # Swift:   call_expression.children[0]          → simple_identifier | navigation_expression
    call_function_field: str   # "function" (Python) / "" = use first child (Swift)

    # Attribute access node (obj.method)
    attribute_type:        str  # "attribute" / "navigation_expression"
    attribute_object_field: str  # "object" / "target"
    attribute_attr_field:  str  # "attribute" / "suffix"

    # Some languages (Swift) nest the method name one level deeper inside the
    # attr node (navigation_suffix → simple_identifier with field "suffix").
    # Set to "" when the attr node itself is the name node.
    attr_name_subfield: str    # "" (Python) / "suffix" (Swift)

    # How to detect "self" — either by text content or by node type
    self_keywords:   frozenset  # {"self", "cls"} — matched against node text
    self_node_type:  str        # "self_expression" (Swift) / "" (match by text)
