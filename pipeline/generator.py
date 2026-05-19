"""
pipeline/generator.py — GraphRAG Generator (Bước 4: Generation)

Nhận context đồ thị từ Retriever và gọi LLM để:
  1. Phân tích issue dựa trên source code liên quan
  2. Dự đoán file nào cần sửa (File Localization)
  3. Giải thích tại sao và gợi ý thay đổi cụ thể

Thiết kế prompt:
  - System prompt ngắn gọn, đặt vai trò "chuyên gia code review"
  - User prompt cấu trúc rõ: Issue → Context → Yêu cầu
  - Context dùng tag [SEED]/[CALLER]/[CALLEE] để LLM hiểu quan hệ
  - Yêu cầu LLM dùng format "FILE: path/to/file.py" để dễ parse

So với Text GraphRAG truyền thống:
  Context ở đây là raw source code (không phải tóm tắt),
  giúp LLM thấy được luồng gọi hàm thực tế thay vì mô tả ngôn ngữ tự nhiên.
"""

from __future__ import annotations

import logging
import re

import anthropic

logger = logging.getLogger(__name__)

# Model và giới hạn token output
_MODEL   = "claude-sonnet-4-6"
_MAX_TOK = 2048

# System prompt ngắn — đặt vai trò và quy tắc trả lời
_SYSTEM = """\
Bạn là chuyên gia phân tích mã nguồn Python. Nhiệm vụ của bạn là đọc mô tả bug/issue \
và đoạn code liên quan được trích xuất từ Knowledge Graph, sau đó xác định các file \
cần sửa đổi để giải quyết issue đó.

Khi trả lời, hãy:
1. Liệt kê các file cần sửa (theo thứ tự ưu tiên), mỗi file trên một dòng dạng: FILE: path/to/file.py
2. Giải thích ngắn gọn tại sao từng file liên quan đến issue
3. Nếu có thể, gợi ý loại thay đổi cần thực hiện (sửa logic, thêm xử lý lỗi, v.v.)
"""

# Template user prompt — {issue_text} và {context} được điền tại runtime
_PROMPT_TMPL = """\
## Mô tả Issue

{issue_text}

## Code Context từ Knowledge Graph

Dưới đây là source code của các hàm/class liên quan được trích xuất tự động từ đồ thị \
phụ thuộc của repo. [SEED] là node khớp trực tiếp với issue. [CALLER] gọi đến seed. \
[CALLEE] được seed gọi đến.

{context}

## Yêu cầu

Dựa vào issue và code context trên, hãy xác định:
1. File nào cần sửa? (dạng FILE: path/to/file.py)
2. Tại sao file đó liên quan?
3. Gợi ý thay đổi cụ thể nếu có thể suy ra từ code.
"""


def generate(issue_text: str, context: str, candidate_files: list[str]) -> dict:
    """
    Gọi LLM với issue + graph context và trả về phân tích.

    Args:
        issue_text:      Nội dung issue/bug report gốc
        context:         Chuỗi source code từ GraphRetriever.retrieve()
        candidate_files: File candidates từ graph (fallback nếu LLM fail)

    Returns:
        dict gồm:
          answer          — câu trả lời đầy đủ từ LLM (markdown)
          predicted_files — list file LLM dự đoán, trích từ "FILE: ..." patterns
          input_tokens    — số token input (dùng để monitor chi phí)
          output_tokens   — số token output
    """
    prompt = _PROMPT_TMPL.format(
        issue_text=issue_text.strip(),
        # Khi không có context (graph rỗng), thông báo để LLM biết giới hạn
        context=context if context else "(Không tìm thấy code liên quan trong đồ thị.)",
    )

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOK,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        answer    = response.content[0].text
        predicted = _extract_files_from_answer(answer)
        return {
            "answer":          answer,
            "predicted_files": predicted,
            "input_tokens":    response.usage.input_tokens,
            "output_tokens":   response.usage.output_tokens,
        }
    except Exception as e:
        logger.error(f"LLM generation error: {e}")
        # Graceful degradation: trả về candidate_files từ graph thay vì crash
        return {
            "answer":          f"Lỗi khi gọi LLM: {e}",
            "predicted_files": candidate_files,
            "input_tokens":    0,
            "output_tokens":   0,
        }


def _extract_files_from_answer(answer: str) -> list[str]:
    """
    Trích file paths từ câu trả lời LLM theo hai pattern:

      1. "FILE: path/to/file.py"    — format yêu cầu trong prompt
      2. "`path/to/file.py`"        — backtick-quoted (LLM hay dùng trong markdown)

    Dùng dict.fromkeys() thay set để giữ thứ tự xuất hiện (file đầu tiên
    là dự đoán ưu tiên nhất của LLM).
    """
    # Pattern 1: explicit FILE: marker
    pattern  = re.compile(r'FILE:\s*([\w/\-\.]+\.py)', re.IGNORECASE)
    found    = pattern.findall(answer)

    # Pattern 2: backtick-quoted .py path
    backtick = re.compile(r'`([\w/\-\.]+\.py)`')
    found   += backtick.findall(answer)

    return list(dict.fromkeys(found))  # deduplicate, preserve order
