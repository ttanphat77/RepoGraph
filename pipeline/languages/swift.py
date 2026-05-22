"""
pipeline/languages/swift.py — LanguageExtractor cho Swift.

Node type mapping (tree-sitter-swift 0.7.2):
  class/struct/enum → class_declaration  (declaration_kind field = "class"/"struct"/"enum")
  function          → function_declaration
  call              → call_expression
  import            → import_declaration
  obj.method        → navigation_expression  (target + suffix fields)
  self              → self_expression node type
"""

from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_swift as tsswift

from pipeline.languages.base import LanguageExtractor

_SWIFT_LANGUAGE = Language(tsswift.language())
_parser = Parser(_SWIFT_LANGUAGE)

swift_extractor = LanguageExtractor(
    parser=_parser,

    builtins=frozenset({
        "print", "debugPrint", "dump", "type", "assert", "precondition",
        "fatalError", "abort", "exit", "Swift", "Foundation",
        "min", "max", "abs", "stride", "zip", "enumerated",
        "Int", "Int8", "Int16", "Int32", "Int64",
        "UInt", "UInt8", "UInt16", "UInt32", "UInt64",
        "Float", "Double", "Bool", "String", "Character",
        "Array", "Dictionary", "Set", "Optional", "Result",
    }),

    function_types=("function_declaration",),
    # class_declaration covers class / struct / enum / actor in Swift tree-sitter
    class_types=("class_declaration",),

    call_type="call_expression",
    import_type="import_declaration",
    from_import_type="",        # Swift has no "from X import Y"
    assignment_types=("property_declaration",),

    # Swift imports: `import Foundation` — module name is `identifier` child (no field)
    import_name_types=("identifier",),
    aliased_import_type="",     # Swift doesn't alias imports
    import_as_names_type="",
    wildcard_import_type="",
    import_keyword_type="import",
    identifier_type="simple_identifier",

    name_field="name",
    params_field="",            # Swift params are inline, no single named field
    superclasses_field="",      # Swift uses inheritance_specifier children, not a field
    module_name_field="",       # Swift import has no module_name field
    alias_name_field="",
    alias_alias_field="",

    # call_expression.children[0] is the function — no named field
    call_function_field="",

    # obj.method → navigation_expression
    attribute_type="navigation_expression",
    attribute_object_field="target",
    attribute_attr_field="suffix",      # navigation_suffix node
    attr_name_subfield="suffix",        # simple_identifier inside navigation_suffix

    # Swift uses `self_expression` node type instead of text "self"
    self_keywords=frozenset(),
    self_node_type="self_expression",
)
