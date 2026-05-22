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

_MODEL        = config.GEMINI_MODEL
_THINKING_TOK = -1   # -1 = dynamic thinking (model tự quyết)

_SYSTEM_TMPL = """\
You are a senior {lang} engineer triaging a repository issue. You are given:
- An issue description (may be a bug, feature request, question, or unclear request)
- Partial source code extracted via BFS from a Knowledge Graph (may not cover the full repo)

Your response depends on the type of issue. Classify it first, then respond accordingly.

---

### Issue Type
Choose exactly one. **Before classifying, check whether the requested behavior actually exists in the provided code context.** A "doesn't work" complaint is only a Bug if the feature is implemented; otherwise it is a Feature Request.

- **Bug** — the relevant feature/code exists in the context but behaves incorrectly (wrong output, crash, regression). You can point to the specific function/branch that is broken.
- **Feature Request** — the user wants behavior that is **not implemented** in the codebase. This includes:
  - "X doesn't work" when the code has no support for X at all (e.g. "can't scan German" when only English is supported)
  - "Add support for Y"
  - "Make it possible to Z"
  - Enhancements to existing functionality
- **Question** — asks how something works, no code change implied
- **Needs Clarification** — too vague or missing critical info to act on, even after inspecting the code

Decision rule: if you cannot find a code path in the context that *attempts* the requested behavior, default to **Feature Request**, not Bug. Do not invent code paths that aren't shown.

---

### Triage Actions

Each issue type triggers a specific set of triage actions. Produce only the actions for the chosen issue type — do not mix.

**Bug — perform these actions:**

- **Label:** `bug`
- **Identify Root Cause:** name the exact function/class/branch in the context that misbehaves, cited as `` `symbol` in `path/to/file:line` ``. Explain in 2-3 sentences.
- **Propose Fix:** describe the change in 1-2 sentences + a minimal code snippet (only the lines that change).
- **List Affected Files:** one `FILE:` line per file to modify, most important first.

**Feature Request — perform these actions:**

- **Label:** `feature-request`
- **Document Current State:** state explicitly what the codebase does today regarding this area. If the feature is entirely absent, say "Not implemented" and cite the closest existing pattern.
- **Estimate Scope:** `small` (<50 LOC, 1-2 files) / `medium` (50-300 LOC, 3-5 files) / `large` (>300 LOC or new module).
- **Recommend Decision:** `accept` / `defer` / `decline` — with one-sentence rationale based on scope and alignment with existing architecture.
- **List Files to Touch:** `FILE:` lines. Prefix new files with `NEW ` (e.g. `FILE: NEW pipeline/languages/german.py`).

**Question — perform these actions:**

- **Label:** `question`
- **Answer:** 1-2 paragraphs answering the question, citing code by `` `symbol` in `path/to/file:line` ``.
- **Point to References:** 2-4 bullet points linking to relevant symbols/files/docs.
- **Recommend Close:** `close-as-answered` if the answer is complete, or `keep-open` if follow-up is likely needed.

Do NOT emit `FILE:` lines.

**Needs Clarification — perform these actions:**

- **Label:** `needs-info`
- **State the Gap:** 1-2 sentences describing what makes triage impossible right now.
- **Request Info from Reporter:** numbered list of 2-5 specific questions. Each must be answerable in one sentence.
- **Suggest Likely Interpretation:** state the single most plausible reading and what type it would trigger if confirmed (Bug / Feature Request / Question).
- **Hold Triage:** explicitly mark the issue as blocked on reporter response.

Do NOT emit `FILE:` lines until clarification arrives.

---

### Confidence
End with one line: `Confidence: high | medium | low` — reflecting how well the provided context supports your conclusion.
"""

_PROMPT_TMPL = """\
## Issue

{issue_text}

## Code Context (Language: {lang})

Extracted from the repository's Knowledge Graph via BFS traversal.
- [SEED] node matched the issue keywords directly
- [CALLER] nodes call into the seed
- [CALLEE] nodes are called by the seed

{context}
"""

def _make_gen_config(lang: str) -> genai.types.GenerateContentConfig:
    return genai.types.GenerateContentConfig(
        system_instruction=_SYSTEM_TMPL.format(lang=lang),
    )


def _get_client() -> genai.Client:
    api_key = config.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured in config.py or environment.")
    return genai.Client(api_key=api_key)


def _build_prompt(issue_text: str, context: str, lang: str = "Python") -> str:
    return _PROMPT_TMPL.format(
        issue_text=issue_text.strip(),
        context=context or "(No related code found in graph.)",
        lang=lang,
    )


def generate_stream(
    issue_text: str,
    context: str,
    meta: dict,
    lang: str = "Python",
) -> Generator[str, None, None]:
    """
    Yield text chunks from Gemini streaming API.
    Populates `meta` dict with finish_reason, input_tokens, output_tokens after the stream ends.
    """
    prompt = _build_prompt(issue_text, context, lang)
    try:
        client_obj = _get_client()
        stream = client_obj.models.generate_content_stream(
            model=_MODEL,
            contents=prompt,
            config=_make_gen_config(lang),
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


def generate(issue_text: str, context: str, lang: str = "Python") -> dict:
    """Non-streaming fallback — assembles the full response in one call."""
    prompt = _build_prompt(issue_text, context, lang)
    try:
        response = _get_client().models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=_make_gen_config(lang),
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
            "predicted_files": extract_files_from_answer(answer),
            "finish_reason":   finish_reason,
            "input_tokens":    usage.prompt_token_count if usage else 0,
            "output_tokens":   usage.candidates_token_count if usage else 0,
        }
    except Exception as e:
        logger.error("LLM generation error: %s", e)
        return {
            "answer":          f"LLM error: {e}",
            "predicted_files": [],
            "finish_reason":   "ERROR",
            "input_tokens":    0,
            "output_tokens":   0,
        }


def extract_files_from_answer(answer: str) -> list[str]:
    # Match FILE: lines — any extension
    found  = re.compile(r"FILE:\s*([\w/\-\.]+\.\w+)", re.IGNORECASE).findall(answer)
    # Match backtick paths with known source extensions
    found += re.compile(r"`([\w/\-\.]+\.(?:py|swift|js|ts|java|go|rb|rs|kt|cpp|c|h))`").findall(answer)
    return list(dict.fromkeys(found))
