"""
Evaluation Module — Phase 2 (10 pts)

Evaluates:
  1. Urgency classification quality  (distribution, coverage, label balance)
  2. AI response quality             (length, structure, language, actionability)
  3. Dataset / feature completeness  (field coverage, date parse rate)
  4. Full unified evaluation report
"""

import re
from collections import Counter
from datetime import datetime

from .features import classify_urgency, compute_urgency_score


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

_DATE_FMTS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%A, %d %B %Y - %H:%M", "%d %B %Y - %H:%M",
    "%A, %d %B %Y", "%d %B %Y",
]


def _can_parse_date(date_str: str) -> bool:
    for fmt in _DATE_FMTS:
        try:
            datetime.strptime((date_str or "").strip(), fmt)
            return True
        except (ValueError, AttributeError):
            continue
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 1. Urgency classification evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_urgency_classification(tasks: list) -> dict:
    """
    Analyse the quality and distribution of urgency labels.

    Metrics:
      - Label distribution (count + %)
      - Date parse coverage
      - Label diversity score (how well-spread the labels are across classes)
    """
    total = max(len(tasks), 1)

    labels   = [classify_urgency(t.get("due_date", "")) for t in tasks]
    counts   = Counter(labels)
    parseable = sum(1 for t in tasks if _can_parse_date(t.get("due_date", "")))

    distribution = {
        label: {
            "count": cnt,
            "pct":   round(cnt / total * 100, 1),
        }
        for label, cnt in counts.items()
    }

    # Label diversity: entropy-based (max when all 5 classes are equal)
    n_classes   = len(counts)
    probs       = [cnt / total for cnt in counts.values()]
    import math
    entropy     = -sum(p * math.log(p + 1e-9) for p in probs)
    max_entropy = math.log(5)  # 5 possible labels
    diversity   = round(entropy / max_entropy * 100, 1)

    return {
        "distribution":    distribution,
        "total_tasks":     total,
        "coverage_pct":    round(parseable / total * 100, 1),
        "n_labels_used":   n_classes,
        "diversity_score": diversity,         # 100 = perfectly balanced
        "most_common":     counts.most_common(1)[0][0] if counts else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. AI response quality evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_ai_response(response_text: str) -> dict:
    """
    Score a single AI-generated text on 4 quality dimensions:
      - Length adequacy    (0.0 – 1.0)
      - Structure          (has bullet/numbered list)
      - Language match     (Arabic expected)
      - Actionability      (contains actionable verbs)

    Returns scores + overall quality (0 – 100).
    """
    if not response_text or not response_text.strip():
        return {"overall_score": 0, "error": "empty response"}

    text   = response_text.strip()
    length = len(text)

    # Length
    if length < 20:
        length_score = 0.2
    elif length < 50:
        length_score = 0.5
    elif length <= 600:
        length_score = 1.0
    else:
        length_score = 0.8   # slightly verbose

    # Structure (bullet / numbered list)
    has_structure  = bool(re.search(r"(\n[-•*•]|\n\d+[.)])", text))
    structure_score = 1.0 if has_structure else 0.4

    # Language (Arabic)
    has_arabic  = bool(re.search(r"[؀-ۿ]", text))
    lang_score  = 1.0 if has_arabic else 0.6

    # Actionability (Arabic + English action verbs)
    action_rx = re.compile(
        r"اعمل|ابدأ|خلص|سلم|راجع|حل|افتح|اكتب|ذاكر|"
        r"submit|complete|finish|start|review|write|study|do",
        re.IGNORECASE,
    )
    action_score = 1.0 if action_rx.search(text) else 0.5

    overall = round(
        (length_score * 0.30 +
         structure_score * 0.30 +
         lang_score     * 0.20 +
         action_score   * 0.20) * 100,
        1,
    )

    return {
        "length_chars":    length,
        "length_score":    round(length_score,   2),
        "structure_score": round(structure_score, 2),
        "language_score":  round(lang_score,      2),
        "action_score":    round(action_score,    2),
        "overall_score":   overall,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dataset completeness evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_dataset_quality(tasks: list) -> dict:
    """
    Measure field completeness and feature extraction coverage.
    """
    total        = max(len(tasks), 1)
    has_title    = sum(1 for t in tasks if t.get("title",    "").strip())
    has_course   = sum(1 for t in tasks if t.get("course",   "").strip() not in ("", "Unknown"))
    has_due_date = sum(1 for t in tasks if t.get("due_date", "").strip())
    date_parsed  = sum(1 for t in tasks if _can_parse_date(t.get("due_date", "")))

    completeness = round((has_title + has_course + has_due_date) / (total * 3) * 100, 1)

    return {
        "total_tasks":            total,
        "title_completeness_pct":    round(has_title    / total * 100, 1),
        "course_completeness_pct":   round(has_course   / total * 100, 1),
        "due_date_completeness_pct": round(has_due_date / total * 100, 1),
        "date_parse_rate_pct":       round(date_parsed  / total * 100, 1),
        "overall_completeness_pct":  completeness,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Full evaluation report
# ─────────────────────────────────────────────────────────────────────────────

def generate_evaluation_report(tasks: list) -> dict:
    """
    Run all evaluations and return a unified structured report.
    """
    urgency_eval = evaluate_urgency_classification(tasks)
    dataset_eval = evaluate_dataset_quality(tasks)

    scores      = [compute_urgency_score(t.get("due_date", "")) for t in tasks]
    avg_urgency = round(sum(scores) / max(len(scores), 1), 1)

    dist = urgency_eval["distribution"]

    return {
        "urgency_classification": urgency_eval,
        "dataset_quality":        dataset_eval,
        "urgency_score_stats": {
            "avg": avg_urgency,
            "max": max(scores, default=0),
            "min": min(scores, default=0),
        },
        "summary": {
            "total_tasks":       len(tasks),
            "overdue_count":     dist.get("overdue",  {}).get("count", 0),
            "urgent_count":      dist.get("urgent",   {}).get("count", 0),
            "soon_count":        dist.get("soon",     {}).get("count", 0),
            "upcoming_count":    dist.get("upcoming", {}).get("count", 0),
            "date_coverage_pct": urgency_eval["coverage_pct"],
            "data_quality_pct":  dataset_eval["overall_completeness_pct"],
            "avg_urgency_score": avg_urgency,
        },
    }
