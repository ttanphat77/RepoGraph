"""
pipeline/generator.py — GraphRAG Generator (Step 4: Generation)
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Generator

import google.genai as genai

import config

logger = logging.getLogger(__name__)

_MODEL        = "gemini-2.5-flash"
_THINKING_TOK = -1   # -1 = dynamic thinking (model tự quyết)

_SYSTEM = """\
You are an expert Python code analyst. Your job is to read a bug/issue description and \
relevant source code extracted from a Knowledge Graph, then identify which files need to \
be modified and propose a concrete fix.

Always respond using the following markdown structure:

---

### 🔍 Root Cause Analysis
[1-2 sentences summarizing the problem in technical terms to confirm you understood the intent.]

**Root cause:** [Explain why this bug occurs based on the current architecture.]

---

### 📂 Technical Context
The following components were retrieved and analyzed to produce the solution:
- **Primary file:** `path/to/file.py` (Lines X – Y)
- **Related dependencies:**
  - Function `A()` in `path/to/helper.py`
  - Class `B` in `path/to/other.py`
- *(Optional)* **Related docs/commits:** e.g. matches the data model defined in `docs/architecture.md`.

---

### 💡 Proposed Fix
[One sentence describing the approach, e.g. "Add input validation in function X to handle the empty-list edge case."]

```python
# path/to/file.py

def affected_function(data):
    # [Agent note: initialize X to handle edge case]
    ...
```

---

### 📋 Files to Modify
List every file that needs a change, one per line, in priority order:
FILE: path/to/file.py
"""

_PROMPT_TMPL = """\
## Issue Description

{issue_text}

## Code Context from Knowledge Graph

The source code below was automatically extracted from the repo's dependency graph.
[SEED] = node that directly matches the issue keywords.
[CALLER] = functions/classes that call the seed node.
[CALLEE] = functions/classes called by the seed node.

{context}

## Task

Using the issue description and code context above, produce a response in the required format:
1. Diagnose the root cause.
2. List the relevant files and dependencies.
3. Propose a concrete code fix with a snippet.
4. End with FILE: lines for every file that must be modified.
"""

_GEN_CONFIG = genai.types.GenerateContentConfig(
    system_instruction=_SYSTEM,
    thinking_config=genai.types.ThinkingConfig(thinking_budget=_THINKING_TOK),
)


def _get_client() -> genai.Client:
    api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured in config.py or environment.")
    return genai.Client(api_key=api_key)


def _build_prompt(issue_text: str, context: str) -> str:
    return _PROMPT_TMPL.format(
        issue_text=issue_text.strip(),
        context=context or "(No related code found in graph.)",
    )


def generate_stream(
    issue_text: str,
    context: str,
    candidate_files: list[str],
    meta: dict,
) -> Generator[str, None, None]:
    """
    Yield text chunks from Gemini streaming API.
    Populates `meta` dict with finish_reason, input_tokens, output_tokens after the stream ends.
    """
    prompt = _build_prompt(issue_text, context)
    try:
        client_obj = _get_client()
        stream = client_obj.models.generate_content_stream(
            model=_MODEL,
            contents=prompt,
            config=_GEN_CONFIG,
        )
        for chunk in stream:
            text = chunk.text or ""
            if text:
                yield text
            if chunk.usage_metadata:
                u = chunk.usage_metadata
                meta["input_tokens"]  = u.prompt_token_count or 0
                meta["output_tokens"] = u.candidates_token_count or 0
            if chunk.candidates:
                meta["finish_reason"] = str(chunk.candidates[0].finish_reason)
        meta.setdefault("finish_reason", "STOP")
    except Exception as e:
        msg = str(e).lower()
        if "closed" in msg or "cancel" in msg or "interrupt" in msg:
            # user stopped the Streamlit script — exit silently
            meta.setdefault("finish_reason", "INTERRUPTED")
            return
        logger.error("LLM streaming error: %s", e)
        meta.update({"finish_reason": "ERROR", "input_tokens": 0, "output_tokens": 0})
        yield f"\n\n*LLM error: {e}*"


def generate(issue_text: str, context: str, candidate_files: list[str]) -> dict:
    """Non-streaming fallback — assembles the full response in one call."""
    prompt = _build_prompt(issue_text, context)
    try:
        response = _get_client().models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=_GEN_CONFIG,
        )
        candidate = response.candidates[0] if response.candidates else None
        finish_reason = str(candidate.finish_reason) if candidate else "NO_CANDIDATE"
        answer = response.text or ""
        usage = response.usage_metadata
        logger.info("finish_reason=%s in=%s out=%s",
                    finish_reason,
                    usage.prompt_token_count if usage else 0,
                    usage.candidates_token_count if usage else 0)
        return {
            "answer":          answer,
            "predicted_files": _extract_files_from_answer(answer),
            "finish_reason":   finish_reason,
            "input_tokens":    usage.prompt_token_count if usage else 0,
            "output_tokens":   usage.candidates_token_count if usage else 0,
        }
    except Exception as e:
        logger.error("LLM generation error: %s", e)
        return {
            "answer":          f"LLM error: {e}",
            "predicted_files": candidate_files,
            "finish_reason":   "ERROR",
            "input_tokens":    0,
            "output_tokens":   0,
        }


def _extract_files_from_answer(answer: str) -> list[str]:
    found  = re.compile(r"FILE:\s*([\w/\-\.]+\.py)", re.IGNORECASE).findall(answer)
    found += re.compile(r"`([\w/\-\.]+\.py)`").findall(answer)
    return list(dict.fromkeys(found))
