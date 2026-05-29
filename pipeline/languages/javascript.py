"""
pipeline/languages/javascript.py — LanguageExtractor cho JavaScript.

Node types verified từ tree-sitter-javascript src/node-types.json:

  call_expression   : field "function" → callee
  member_expression : field "object", field "property"  (KHÔNG phải "attribute")
  class_declaration : field "name", child class_heritage (không phải named field)
  import_statement  : field "source" → tên module
    import_clause → named_imports → import_specifier
      field "name" → tên gốc, field "alias" → tên local
  arrow_function    : field "parameters" (nhiều param) hoặc "parameter" (một param)
"""

from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjs

from pipeline.languages.base import LanguageExtractor

try:
    _JS_LANGUAGE = Language(tsjs.language())
    _parser = Parser(_JS_LANGUAGE)
except TypeError:
    _JS_LANGUAGE = Language(tsjs.language(), "javascript")
    _parser = Parser()
    _parser.set_language(_JS_LANGUAGE)

javascript_extractor = LanguageExtractor(
    parser=_parser,

    builtins=frozenset({
        "console", "Math", "JSON", "Object", "Array", "String", "Number",
        "Boolean", "Promise", "Error", "Symbol", "Map", "Set", "WeakMap",
        "WeakSet", "Date", "RegExp", "Proxy", "Reflect",
        "parseInt", "parseFloat", "isNaN", "isFinite",
        "setTimeout", "setInterval", "clearTimeout", "clearInterval",
        "fetch", "require", "module", "exports",
        "__dirname", "__filename", "process", "Buffer", "global",
        "undefined", "null", "NaN", "Infinity",
    }),

    # function_expression và arrow_function bị loại vì không có field "name" đáng tin cậy
    # (tên lấy từ variable_declarator bên ngoài — engine chưa xử lý trường hợp này)
    function_types=("function_declaration", "method_definition"),
    class_types=("class_declaration", "class_expression"),

    call_type="call_expression",
    import_type="import_statement",
    from_import_type="",
    assignment_types=("variable_declarator", "lexical_declaration", "variable_declaration", "assignment_expression"),

    import_name_types=("import_specifier", "identifier"),
    aliased_import_type="import_specifier",
    import_as_names_type="named_imports",
    wildcard_import_type="namespace_import",
    import_keyword_type="import",
    identifier_type="identifier",

    name_field="name",
    params_field="parameters",
    superclasses_field="",          # class_heritage là child node, không phải named field
    module_name_field="source",
    alias_name_field="name",
    alias_alias_field="alias",

    call_function_field="function",
    attribute_type="member_expression",
    attribute_object_field="object",
    attribute_attr_field="property", # "property", KHÔNG phải "attribute"
    attr_name_subfield="",

    self_keywords=frozenset({"this"}),
    self_node_type="",

    source_extensions=(".js", ".mjs", ".cjs"),
    index_file_name="index",
    uses_js_imports=True,
    anon_function_types=("arrow_function", "function_expression"),
    new_expression_type="new_expression",
)
