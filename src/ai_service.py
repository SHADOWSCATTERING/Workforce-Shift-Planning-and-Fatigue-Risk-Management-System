"""
ai_service.py
---------------
The AI / Innovation layer of the system.

Design principle (see fatigue_engine.py docstring): the AI NEVER computes
risk scores or rest-hour math itself. It is handed the deterministic
output of FatigueEngine and asked only to:
  1. Explain WHY a schedule is risky, in plain English a non-technical
     shift manager can understand.
  2. Summarize/rank the most urgent issues.
  3. Phrase rule-based "safer alternative" suggestions in a clear way.

This keeps the system auditable: every number the AI talks about can be
traced back to a specific rule in fatigue_rules.csv, and the AI cannot
invent a violation that the engine didn't actually find.

If ANTHROPIC_API_KEY is not set (or the API call fails for any reason -
network, rate limit, etc.), the service transparently falls back to a
template-based explanation generator so the product still works end to
end for grading/demo purposes. The response always includes a `source`
field ("ai" or "fallback_template") so callers/UI can be honest about
which path produced the text - this doubles as the project's required
"limitations / responsible-use" disclosure.
"""
import os
import json
import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
REQUEST_TIMEOUT_SECONDS = 20

SYSTEM_PROMPT = (
    "You are a workforce safety assistant embedded in a shift-planning tool. "
    "You will be given a JSON object containing a fatigue-risk analysis that was "
    "already computed by deterministic rule-based code (rest hours, consecutive "
    "days, weekly hours, shift overlaps). Do NOT invent, recompute, or contradict "
    "any numbers in that JSON - treat them as ground truth. Your job is only to:\n"
    "1) Explain, in 2-4 plain-English sentences a shift manager (non-technical) "
    "would understand, why this employee's schedule is risky right now.\n"
    "2) List the single most urgent issue first.\n"
    "3) If safer_alternatives are provided, briefly recommend one and say why.\n"
    "Keep the tone calm and factual, never alarmist. If the data shows no "
    "violations, say clearly that the schedule looks safe. Respond with ONLY a "
    "JSON object (no markdown fences, no preamble) with this exact shape: "
    '{"explanation": "...", "most_urgent_issue": "...", "recommendation": "..."}'
)


def _call_anthropic(analysis: dict, safer_alternatives: list = None) -> dict | None:
    if not ANTHROPIC_API_KEY:
        return None

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": json.dumps({
                    "fatigue_analysis": analysis,
                    "safer_alternatives": safer_alternatives or [],
                }, default=str),
            }
        ],
    }
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload,
                              timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
        text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
        raw_text = "".join(text_parts).strip()
        raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw_text)
        parsed["source"] = "ai"
        return parsed
    except Exception as exc:
        # Network issues, bad key, rate limits, malformed JSON from the model, etc.
        # We never let an AI failure break the user-facing feature.
        print(f"[ai_service] Anthropic API call failed, using fallback. Reason: {exc}")
        return None


def _fallback_explanation(analysis: dict, safer_alternatives: list = None) -> dict:
    """Deterministic, template-based explanation used when no API key is
    configured or the AI call fails. Ensures the feature always works."""
    violations = analysis.get("violations", [])
    name = analysis.get("employee_name", "This employee")
    risk_level = analysis.get("risk_level", "Low")

    if not violations:
        return {
            "explanation": f"{name}'s current schedule does not breach any fatigue-risk rules. "
                            f"Rest periods, consecutive working days, and weekly hours are all within safe limits.",
            "most_urgent_issue": "None detected.",
            "recommendation": "No changes needed. Continue monitoring as new shifts are added.",
            "source": "fallback_template",
        }

    # Sort by severity so the most urgent issue is genuinely most urgent
    severity_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    sorted_v = sorted(violations, key=lambda v: severity_rank.get(v.get("severity", "Low"), 3))
    top = sorted_v[0]

    other_count = len(violations) - 1
    other_clause = f" There {'is' if other_count == 1 else 'are'} also {other_count} additional issue{'s' if other_count != 1 else ''} flagged." if other_count > 0 else ""

    explanation = (
        f"{name}'s schedule is currently rated {risk_level} risk, mainly because of: "
        f"{top['detail']}{other_clause} Schedules like this increase the chance of "
        f"reduced alertness, errors, and burnout, and may also breach workplace safety guidelines."
    )

    if safer_alternatives:
        best = safer_alternatives[0]
        recommendation = (
            f"Consider this adjustment: {best['option']} (new shift: {best['shift_date']} "
            f"{best['start_time']}-{best['end_time']}), which is projected to bring the risk "
            f"level down to {best['projected_risk_level']}."
        )
    else:
        recommendation = (
            "Review the flagged shift(s) with the employee and adjust timing, add a rest day, "
            "or reassign part of the workload to reduce risk."
        )

    return {
        "explanation": explanation,
        "most_urgent_issue": f"[{top['rule_id']}] {top['rule_name']}: {top['detail']}",
        "recommendation": recommendation,
        "source": "fallback_template",
    }


def explain_fatigue_risk(analysis: dict, safer_alternatives: list = None) -> dict:
    """Main entry point used by the API layer. Returns a dict with
    explanation / most_urgent_issue / recommendation / source."""
    ai_result = _call_anthropic(analysis, safer_alternatives)
    if ai_result is not None:
        return ai_result
    return _fallback_explanation(analysis, safer_alternatives)


def explain_conflict(conflict_detail: dict) -> dict:
    """Smaller, focused explanation for a single hard conflict (e.g. a
    double-booking) surfaced at shift-creation time."""
    analysis_stub = {
        "employee_name": conflict_detail.get("employee_name", "This employee"),
        "risk_level": "Critical",
        "violations": [conflict_detail],
    }
    return explain_fatigue_risk(analysis_stub)


def is_ai_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)
