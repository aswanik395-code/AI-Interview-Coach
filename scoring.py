"""Deterministic scoring. The LLM only supplies 0-10 sub-scores; every final number is computed here."""

WEIGHTS = {"correctness": 0.5, "depth": 0.3, "clarity": 0.2}
RED_FLAG_PENALTY = 10  # points off a single answer (0-100 scale)
BANDS = [(85, "Strong"), (70, "Good"), (55, "Borderline"), (0, "Needs improvement")]
FORMULA = ("answer score = 10 x (0.5*correctness + 0.3*depth + 0.2*clarity) - 10 if red flag (min 0); "
           "overall = mean of answer scores; skipped questions count as 0.")


def clamp_int(value, lo=0, hi=10):
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = lo
    return max(lo, min(hi, value))


def _str_list(value, limit=3):
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:200] for v in value if str(v).strip()][:limit]


def normalize_eval(raw, skipped=False):
    """Coerce whatever the LLM returned into a safe, fixed-shape evaluation."""
    if skipped:
        return {"correctness": 0, "depth": 0, "clarity": 0, "strengths": [],
                "weaknesses": ["Question was skipped"], "feedback": "Skipped.",
                "red_flag": False, "skipped": True}
    raw = raw if isinstance(raw, dict) else {}
    return {
        "correctness": clamp_int(raw.get("correctness")),
        "depth": clamp_int(raw.get("depth")),
        "clarity": clamp_int(raw.get("clarity")),
        "strengths": _str_list(raw.get("strengths")),
        "weaknesses": _str_list(raw.get("weaknesses")),
        "feedback": str(raw.get("feedback", "")).strip()[:500],
        "red_flag": bool(raw.get("red_flag", False)),
        "skipped": False,
    }


def score_answer(ev):
    base = 10 * sum(ev[k] * w for k, w in WEIGHTS.items())
    penalty = RED_FLAG_PENALTY if ev.get("red_flag") else 0
    return round(max(0.0, base - penalty), 1)


def rating_for(score):
    for threshold, label in BANDS:
        if score >= threshold:
            return label
    return BANDS[-1][1]


def score_interview(evals):
    if not evals:
        return {"overall": 0.0, "rating": rating_for(0), "dimension_averages": {k: 0.0 for k in WEIGHTS},
                "per_answer": [], "red_flags": 0, "answered": 0, "skipped": 0, "formula": FORMULA}
    per_answer = [score_answer(e) for e in evals]
    overall = round(sum(per_answer) / len(per_answer), 1)
    return {
        "overall": overall,
        "rating": rating_for(overall),
        "dimension_averages": {k: round(sum(e[k] for e in evals) / len(evals), 2) for k in WEIGHTS},
        "per_answer": per_answer,
        "red_flags": sum(1 for e in evals if e.get("red_flag")),
        "answered": sum(1 for e in evals if not e.get("skipped")),
        "skipped": sum(1 for e in evals if e.get("skipped")),
        "formula": FORMULA,
    }
