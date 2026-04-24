from pipeline.schemas.base import SchemaPlugin
from pipeline.schemas.simple import SimpleSchema
from pipeline.schemas.detailed import DetailedSchema

_REGISTRY: dict[str, type[SchemaPlugin]] = {
    "simple": SimpleSchema,
    "detailed": DetailedSchema,
}


def load_schema(name: str) -> SchemaPlugin:
    if name not in _REGISTRY:
        available = ", ".join(f'"{k}"' for k in _REGISTRY)
        raise ValueError(f"Unknown schema {name!r}. Available: {available}")
    return _REGISTRY[name]()
