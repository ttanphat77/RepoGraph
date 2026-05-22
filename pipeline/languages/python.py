"""
pipeline/languages/python.py — LanguageExtractor cho Python.
"""

from __future__ import annotations

from tree_sitter import Language, Parser
import tree_sitter_python as tspython

from pipeline.languages.base import LanguageExtractor

try:
    _PY_LANGUAGE = Language(tspython.language())
    _parser = Parser(_PY_LANGUAGE)
except TypeError:
    # tree-sitter < 0.22
    _PY_LANGUAGE = Language(tspython.language(), "python")
    _parser = Parser()
    _parser.set_language(_PY_LANGUAGE)

python_extractor = LanguageExtractor(
    parser=_parser,

    builtins=frozenset({
        "print", "len", "range", "str", "int", "float", "bool", "list", "dict",
        "tuple", "set", "type", "isinstance", "issubclass", "hasattr", "getattr",
        "setattr", "delattr", "super", "object", "enumerate", "zip", "map",
        "filter", "sorted", "reversed", "min", "max", "sum", "abs", "round",
        "open", "repr", "iter", "next", "any", "all", "vars", "dir", "id",
        "hash", "callable", "staticmethod", "classmethod", "property",
    }),

    function_types=("function_definition", "async_function_definition"),
    class_types=("class_definition",),

    call_type="call",
    import_type="import_statement",
    from_import_type="import_from_statement",
    assignment_types=("assignment", "annotated_assignment", "expression_statement"),

    import_name_types=("dotted_name", "aliased_import"),
    aliased_import_type="aliased_import",
    import_as_names_type="import_as_names",
    wildcard_import_type="wildcard_import",
    import_keyword_type="import",
    identifier_type="identifier",

    name_field="name",
    params_field="parameters",
    superclasses_field="superclasses",
    module_name_field="module_name",
    alias_name_field="name",
    alias_alias_field="alias",

    call_function_field="function",
    attribute_type="attribute",
    attribute_object_field="object",
    attribute_attr_field="attribute",
    attr_name_subfield="",

    self_keywords=frozenset({"self", "cls"}),
    self_node_type="",
)
