# =============================================================================
# pipeline/schemas/__init__.py — Schema Registry
#
# Đây là điểm duy nhất để đăng ký và load schema đồ thị.
# Mỗi schema được đại diện bởi một class implement SchemaPlugin.
#
# Cách thêm schema mới:
#   1. Tạo file pipeline/schemas/my_schema.py với class MySchema(SchemaPlugin)
#   2. Import và đăng ký vào _REGISTRY bên dưới
#   3. Đặt ACTIVE_SCHEMA = "my_schema" trong config.py
# =============================================================================

from pipeline.schemas.base import SchemaPlugin
from pipeline.schemas.simple import SimpleSchema
from pipeline.schemas.detailed import DetailedSchema

# Bảng đăng ký schema: tên string → class SchemaPlugin
# Dùng string làm key để config.py có thể chọn schema mà không cần import trực tiếp.
_REGISTRY: dict[str, type[SchemaPlugin]] = {
    "simple":   SimpleSchema,    # Module/Class/Function + Defines/Calls/Imports/Inherits
    "detailed": DetailedSchema,  # Đầy đủ hơn: METHOD, FIELD, GLOBAL_VARIABLE, ...
}


def load_schema(name: str) -> SchemaPlugin:
    """
    Tạo và trả về instance SchemaPlugin theo tên.

    Gọi hàm này mỗi lần cần schema — instance không giữ state toàn cục,
    nên an toàn khi dùng trong multiprocessing (mỗi worker tạo instance riêng).

    Raises:
        ValueError: nếu name không có trong registry.
    """
    if name not in _REGISTRY:
        # Liệt kê các tên hợp lệ để dễ debug
        available = ", ".join(f'"{k}"' for k in _REGISTRY)
        raise ValueError(f"Unknown schema {name!r}. Available: {available}")
    return _REGISTRY[name]()
