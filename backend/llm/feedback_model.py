"""
Semantic Cognitive Debugger — LLM Feedback Module
==================================================
Uses a locally-running Ollama model to produce developer feedback
from root-cause analysis data, error context, and source code.

No external APIs. No hardcoded responses. The LLM reasons over
the full RCA payload and returns structured JSON that the frontend
can render directly.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-coder:1.5b"  # lightweight model; fits in limited RAM
OLLAMA_TIMEOUT = 120.0            # seconds – large models can be slow

MODEL_NAME = "OllamaSemanticDebugger"
MODEL_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Core public function — called from backend/main.py
# ---------------------------------------------------------------------------

def generate_developer_feedback(
    error: dict[str, Any],
    rca: dict[str, Any] | None = None,
    similar_bugs: list[dict[str, Any]] | None = None,
    source_code: str = "",
    model_name: str | None = None,
) -> dict[str, Any]:
    """Build a rich developer feedback payload by querying Ollama.

    The function constructs a detailed prompt from the error, the RCA
    engine output, any similar historical bugs, and the user's source
    code.  The LLM responds with structured JSON which is parsed and
    normalised into the ``DeveloperFeedback`` shape expected by the
    React frontend.

    If Ollama is unreachable the function falls back to a lightweight
    deterministic summary so the frontend never breaks.
    """
    rca = rca or {}
    similar_bugs = similar_bugs or []

    # --- build the prompt ------------------------------------------------
    prompt = _build_prompt(error, rca, similar_bugs, source_code)

    # --- call Ollama -----------------------------------------------------
    try:
        raw_text = _call_ollama(prompt, model_name=model_name)
        feedback = _parse_llm_json(raw_text)
    except Exception as exc:
        logger.warning("Ollama call failed (%s); using deterministic fallback.", exc)
        feedback = _deterministic_fallback(error, rca, similar_bugs)

    # --- normalise into the exact frontend shape -------------------------
    res = _normalise_feedback(feedback, error, rca)
    res["model_name"] = model_name or OLLAMA_MODEL
    return res


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

def _build_prompt(
    error: dict[str, Any],
    rca: dict[str, Any],
    similar_bugs: list[dict[str, Any]],
    source_code: str,
) -> str:
    """Compose the system + user prompt sent to the LLM."""

    system = (
        "You are a senior software debugging assistant integrated into an IDE. "
        "A developer just ran their Python code and hit an error. You have been "
        "given the error details, a root-cause analysis from an automated RCA "
        "engine, similar historical bug-fix records, and the developer's source "
        "code. Your job is to produce a thorough, actionable debugging report.\n\n"
        "RULES:\n"
        "1. Focus on the ROOT CAUSE — not just what the error says, but WHY it happened.\n"
        "2. Provide concrete, specific fix suggestions referencing the actual code.\n"
        "3. If historical bugs are relevant, explain the pattern.\n"
        "4. Be educational — help the developer learn, not just copy-paste.\n"
        "5. Respond ONLY with valid JSON matching the schema below. No markdown fences.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "headline": "One-line summary of what went wrong",\n'
        '  "diagnosis": "Detailed paragraph explaining the full chain of causation",\n'
        '  "root_cause": "Precise technical root cause",\n'
        '  "primary_fix": "The recommended code change to fix this",\n'
        '  "severity": "low | medium | high | critical",\n'
        '  "evidence": ["evidence point 1 (STRING ONLY)", "evidence point 2 (STRING ONLY)"],\n'
        '  "fix_steps": ["step 1 (STRING ONLY)", "step 2 (STRING ONLY)"],\n'
        '  "code_actions": [{"before": "old code", "after": "fixed code"}],\n'
        '  "prevention": ["tip 1 (STRING ONLY)", "tip 2 (STRING ONLY)"],\n'
        '  "validation_checks": ["check 1 (STRING ONLY)", "check 2 (STRING ONLY)"],\n'
        '  "debug_questions": ["question 1 (STRING ONLY)", "question 2 (STRING ONLY)"],\n'
        '  "learning_note": "A helpful educational takeaway"\n'
        "}\n"
    )

    # --- error section ---------------------------------------------------
    error_section = (
        f"EXCEPTION TYPE: {error.get('type') or error.get('exception_type', 'UnknownError')}\n"
        f"ERROR MESSAGE: {error.get('message', '')}\n"
        f"LINE NUMBER: {error.get('line_number', -1)}\n"
        f"FILE: {error.get('file_name', '')}\n"
        f"FAILING FUNCTION: {error.get('failing_function', '') or (error.get('code_context') or {}).get('failing_function', '')}\n"
        f"TRACEBACK:\n{error.get('traceback', '')}\n"
    )

    # --- code context section --------------------------------------------
    code_context = error.get("code_context") or {}
    code_section = ""
    if code_context.get("surrounding_code"):
        code_section += f"SURROUNDING CODE:\n{code_context['surrounding_code']}\n"
    if code_context.get("imports"):
        code_section += f"IMPORTS: {', '.join(code_context['imports'])}\n"
    if source_code:
        # send first 1500 chars to stay within context window
        code_section += f"\nFULL SOURCE CODE (truncated):\n{source_code[:1500]}\n"

    # --- RCA section -----------------------------------------------------
    rca_section = ""
    if rca.get("summary"):
        rca_section += f"RCA SUMMARY: {rca['summary']}\n"
    if rca.get("suggested_fix"):
        rca_section += f"RCA SUGGESTED FIX: {rca['suggested_fix']}\n"
    if rca.get("confidence") is not None:
        rca_section += f"RCA CONFIDENCE: {rca['confidence']}\n"
    if rca.get("matched_patterns"):
        rca_section += "MATCHED HISTORICAL PATTERNS:\n"
        for pat in rca["matched_patterns"][:3]:
            rca_section += (
                f"  - Bug {pat.get('bug_id', '?')} "
                f"(project: {pat.get('project', '?')}, "
                f"score: {pat.get('score', '?')}): "
                f"{pat.get('root_cause', 'no description')}\n"
            )

    # --- similar bugs section --------------------------------------------
    similar_section = ""
    if similar_bugs:
        similar_section = "SIMILAR HISTORICAL BUGS:\n"
        for bug in similar_bugs[:3]:
            meta = bug.get("metadata", {})
            similar_section += (
                f"  Bug ID: {bug.get('bug_id', '?')} | "
                f"Score: {bug.get('score', 0):.2f} | "
                f"Type: {meta.get('exception_type', '?')}\n"
                f"    Root cause: {meta.get('rca_summary', 'N/A')}\n"
                f"    Buggy code: {(meta.get('buggy_code', '') or '')[:150]}\n"
                f"    Fixed code: {(meta.get('fixed_code', '') or '')[:150]}\n"
            )

    user_prompt = (
        "Analyze the following error and produce the JSON debugging report.\n\n"
        f"--- ERROR ---\n{error_section}\n"
        f"--- CODE ---\n{code_section}\n"
        f"--- ROOT CAUSE ANALYSIS ---\n{rca_section}\n"
        f"--- HISTORICAL BUGS ---\n{similar_section}\n"
        "Respond with ONLY the JSON object. No explanation outside the JSON."
    )

    return f"[SYSTEM]\n{system}\n[USER]\n{user_prompt}"


# ---------------------------------------------------------------------------
# Ollama HTTP call
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str, model_name: str | None = None) -> str:
    """Send a generate request to the local Ollama server."""
    payload = {
        "model": model_name or OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.4,
            "num_predict": 1024,
            "num_ctx": 2048,
        },
    }

    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")


# ---------------------------------------------------------------------------
# JSON parsing with resilience
# ---------------------------------------------------------------------------

def _parse_llm_json(raw: str) -> dict[str, Any]:
    """Try hard to extract a JSON object from the LLM's response.

    LLMs sometimes wrap JSON in markdown fences or add preamble text.
    We strip all of that and attempt multiple parse strategies.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    cleaned = cleaned.strip("`").strip()

    # Strategy 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find first { ... } block
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 3: try to fix common issues (trailing commas, etc.)
    try:
        fixed = re.sub(r",\s*([}\]])", r"\1", cleaned)
        match = re.search(r"\{[\s\S]*\}", fixed)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    logger.warning("Could not parse LLM output as JSON; returning raw text in fallback shape.")
    return {"diagnosis": raw.strip()}


# ---------------------------------------------------------------------------
# Normalise into the DeveloperFeedback shape
# ---------------------------------------------------------------------------

def _normalise_feedback(
    feedback: dict[str, Any],
    error: dict[str, Any],
    rca: dict[str, Any],
) -> dict[str, Any]:
    """Ensure every field the frontend expects is present with the right type."""
    exception_type = error.get("type") or error.get("exception_type", "UnknownError")
    line_number = int(error.get("line_number") or -1)
    code_context = error.get("code_context") or {}
    evidence = _list(feedback, "evidence", "observations", "proof")
    fix_steps = _list(
        feedback,
        "fix_steps",
        "developer_fix_plan",
        "fix_plan",
        "repair_steps",
        "recommended_steps",
    )
    code_actions = _list(feedback, "code_actions", "code_changes", "patch_suggestions")
    historical_patterns = _list(feedback, "historical_patterns", "similar_patterns", "matched_patterns")
    prevention = _list(feedback, "prevention", "prevention_checks", "preventive_checks")
    validation_checks = _list(feedback, "validation_checks", "tests", "test_checks")
    debug_questions = _list(
        feedback,
        "debug_questions",
        "debugging_questions",
        "questions",
        "questions_to_ask",
        "follow_up_questions",
    )

    if not evidence:
        evidence = _default_evidence(error, rca)
    if not fix_steps:
        fix_steps = _default_fix_steps(error, rca)
    if not prevention:
        prevention = _default_prevention()
    if not validation_checks:
        validation_checks = _default_validation_checks(exception_type)
    if not debug_questions:
        debug_questions = _default_debug_questions(error)

    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "mode": "ollama",
        "training_record_count": 0,
        "predicted_exception_type": exception_type,
        "headline": _str(feedback, "headline", f"{exception_type} detected"),
        "diagnosis": _str(feedback, "diagnosis", rca.get("summary", "")),
        "root_cause": _str(feedback, "root_cause", rca.get("summary", "")),
        "primary_fix": _str(feedback, "primary_fix", rca.get("suggested_fix", "")),
        "severity": _str(feedback, "severity", "high" if line_number > 0 else "medium"),
        "confidence": float(rca.get("confidence", 0.5)),
        "location": {
            "file": error.get("file_name", ""),
            "line_number": line_number,
            "function": error.get("failing_function", "")
                        or code_context.get("failing_function", ""),
        },
        "evidence": evidence,
        "fix_steps": fix_steps,
        "code_actions": code_actions,
        "historical_patterns": historical_patterns,
        "prevention": prevention,
        "validation_checks": validation_checks,
        "debug_questions": debug_questions,
        "learning_note": _str(feedback, "learning_note", ""),
    }


# ---------------------------------------------------------------------------
# Deterministic fallback (when Ollama is unreachable)
# ---------------------------------------------------------------------------

def _deterministic_fallback(
    error: dict[str, Any],
    rca: dict[str, Any],
    similar_bugs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Produce a minimal but useful feedback dict without the LLM."""
    exception_type = error.get("type") or error.get("exception_type", "UnknownError")
    message = error.get("message", "")
    rca_summary = rca.get("summary", "")
    suggested_fix = rca.get("suggested_fix", "")

    evidence = [
        f"Exception: {exception_type}: {message}",
    ]
    if rca_summary:
        evidence.append(f"RCA engine analysis: {rca_summary}")
    for bug in similar_bugs[:2]:
        meta = bug.get("metadata", {})
        evidence.append(
            f"Similar bug {bug.get('bug_id', '?')} "
            f"(score {bug.get('score', 0):.2f}): {meta.get('rca_summary', 'N/A')}"
        )

    return {
        "headline": f"{exception_type}: {message}" if message else f"{exception_type} detected",
        "diagnosis": rca_summary or f"A {exception_type} was raised. "
                     "The Ollama LLM is not reachable so this is a minimal analysis. "
                     "Please ensure Ollama is running (ollama serve) and try again for a detailed report.",
        "root_cause": rca_summary,
        "primary_fix": suggested_fix or "Review the traceback and inspect the variables at the failing line.",
        "severity": "high",
        "evidence": evidence,
        "fix_steps": [
            "Read the traceback to locate the exact failing line.",
            suggested_fix or "Inspect variable types and values at the point of failure.",
            "Apply the fix and re-run to confirm the error is resolved.",
        ],
        "code_actions": [],
        "prevention": [
            "Add input validation before the operation that failed.",
            "Write a regression test covering this failure case.",
        ],
        "validation_checks": [
            "Re-run the code and verify the error no longer occurs.",
            "Test with edge-case inputs around the failing condition.",
        ],
        "debug_questions": [
            "What are the runtime types and values of variables on the failing line?",
            "Which caller or code path first introduced the invalid state?",
        ],
        "learning_note": "",
    }


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

def _str(d: dict, key: str, default: str = "") -> str:
    val = d.get(key)
    return str(val).strip() if val else default


def _list(d: dict, *keys: str) -> list:
    for key in keys:
        val = d.get(key)
        items = _coerce_list(val)
        if items:
            return items
    return []


def _coerce_list(val: Any) -> list:
    if val is None:
        return []
    if isinstance(val, (list, tuple)):
        return [item for item in val if item not in (None, "")]
    if isinstance(val, dict):
        return [val]
    if isinstance(val, str):
        text = val.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            parsed_items = _coerce_list(parsed)
            if parsed_items:
                return parsed_items
        except json.JSONDecodeError:
            pass
        parts = [
            re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", part).strip()
            for part in text.splitlines()
            if part.strip()
        ]
        return parts or [text]
    return [str(val)]


def _default_evidence(error: dict[str, Any], rca: dict[str, Any]) -> list[str]:
    exception_type = error.get("type") or error.get("exception_type", "UnknownError")
    message = error.get("message", "")
    line_number = error.get("line_number", -1)
    evidence = [f"Exception: {exception_type}: {message}".strip()]
    if line_number and line_number != -1:
        evidence.append(f"Traceback points to line {line_number}.")
    if rca.get("summary"):
        evidence.append(f"RCA engine analysis: {rca['summary']}")
    return evidence


def _default_fix_steps(error: dict[str, Any], rca: dict[str, Any]) -> list[str]:
    steps = ["Inspect the values and types used on the failing line."]
    if rca.get("suggested_fix"):
        steps.append(str(rca["suggested_fix"]))
    steps.append("Apply the smallest fix and re-run the same failing input.")
    return steps


def _default_prevention() -> list[str]:
    return [
        "Add validation around the assumption that failed.",
        "Write a regression test for this exact failure case.",
    ]


def _default_validation_checks(exception_type: str) -> list[str]:
    return [
        f"Re-run the program and confirm {exception_type} no longer occurs.",
        "Test one normal input and one edge-case input around the failing condition.",
    ]


def _default_debug_questions(error: dict[str, Any]) -> list[str]:
    line_number = error.get("line_number", -1)
    target = f"line {line_number}" if line_number and line_number != -1 else "the failing line"
    return [
        f"What are the runtime values and types at {target}?",
        "Which caller or input first created the invalid state?",
    ]


def stream_developer_feedback_generator(
    error: dict[str, Any],
    rca: dict[str, Any] | None = None,
    similar_bugs: list[dict[str, Any]] | None = None,
    source_code: str = "",
    model_name: str | None = None,
) -> typing.Generator[str, None, None]:
    """Stream raw feedback text from Ollama and then yield separator + normalized JSON."""
    import typing
    rca = rca or {}
    similar_bugs = similar_bugs or []
    prompt = _build_prompt(error, rca, similar_bugs, source_code)
    
    selected_model = model_name or OLLAMA_MODEL
    raw_text = ""
    try:
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": 0.4,
                "num_predict": 1024,
                "num_ctx": 2048,
            },
        }
        with httpx.stream("POST", f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT) as r:
            r.raise_for_status()
            for chunk in r.iter_lines():
                if chunk:
                    try:
                        data = json.loads(chunk)
                        response_text = data.get("response", "")
                        raw_text += response_text
                        yield response_text
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("Ollama stream failed (%s); using deterministic fallback.", exc)
        fallback_text = "Ollama connection failed or model not responding. Loading local deterministic fallback...\n"
        yield fallback_text
        raw_text = fallback_text

    feedback = _parse_llm_json(raw_text)
    normalized = _normalise_feedback(feedback, error, rca)
    normalized["model_name"] = selected_model
    
    yield "\n[METADATA_SEPARATOR]\n"
    yield json.dumps(normalized)

