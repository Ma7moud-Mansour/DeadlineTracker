"""
Data Cleaning & Preprocessing Pipeline — Phase 1 Rubric (20 pts)

Pipeline stages:
  1. Whitespace normalization
  2. Task-type prefix stripping from course field
  3. Date string normalization → ISO format
  4. Field validation (required fields, length)
  5. Quality report generation
"""

import re
from datetime import datetime

# ── Task-type prefixes Moodle embeds in the course field ──────────────────────
TASK_TYPE_PREFIXES = [
    "Assignment is due · ",
    "Quiz closes · ",
    "Turnitin Assignment 2 requires action · ",
    "Turnitin Assignment requires action · ",
    "Feedback is due · ",
    "Choice closes · ",
    "Workshop closes · ",
]

# Bare prefixes with no course following them (treated as unknown course)
BARE_PREFIXES = {
    "Assignment is due",
    "Quiz closes",
    "Feedback is due",
    "Choice closes",
    "Workshop closes",
}

# ── Date format patterns Moodle uses ─────────────────────────────────────────
DATE_FORMATS = [
    "%A, %d %B %Y - %H:%M",   # "Wednesday, 15 April 2026 - 12:45"
    "%d %B %Y - %H:%M",        # "15 April 2026 - 12:45"
    "%A, %d %B %Y",            # "Wednesday, 15 April 2026"
    "%d %B %Y",                # "15 April 2026"
]


# ─────────────────────────────────────────────────────────────────────────────
# Individual cleaning helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_task_type(raw_course: str) -> str:
    """Return the task-type label embedded in the raw course string."""
    for prefix in TASK_TYPE_PREFIXES:
        if raw_course.startswith(prefix):
            return prefix.rstrip(" · ")
    if raw_course in BARE_PREFIXES:
        return raw_course
    return "Assignment is due"  # default for unlabelled tasks


def clean_course_name(raw_course: str) -> str:
    """Strip the task-type prefix and return only the course name."""
    for prefix in TASK_TYPE_PREFIXES:
        if raw_course.startswith(prefix):
            return raw_course[len(prefix):].strip()
    # Bare prefix with no real course name
    if raw_course.strip() in BARE_PREFIXES:
        return "Unknown"
    return raw_course.strip()


def normalize_date(raw_date: str):
    """
    Try to parse Moodle's human-readable date string and convert to ISO format.

    Returns:
        (normalized_str, was_parsed_bool)
    """
    cleaned = raw_date.strip()
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S"), True
        except ValueError:
            continue
    # Return original if all formats fail
    return cleaned, False


def validate_task(task: dict):
    """
    Validate a cleaned task dict.

    Returns:
        (is_valid: bool, issues: list[str])
    """
    issues = []
    title = task.get("title", "").strip()
    course = task.get("course", "").strip()
    due_date = task.get("due_date", "").strip()

    if not title:
        issues.append("missing_title")
    elif len(title) < 3:
        issues.append("title_too_short")

    if not course or course == "Unknown":
        issues.append("missing_course")

    if not due_date:
        issues.append("missing_due_date")

    return len(issues) == 0, issues


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_tasks(raw_tasks: list) -> tuple:
    """
    Full preprocessing pipeline for a list of raw scraped task dicts.

    Each raw task is expected to have: title, course, due_date.

    Returns:
        cleaned_tasks   : list of enriched/cleaned task dicts
        quality_report  : dict with completeness metrics and per-field stats
    """
    cleaned_tasks = []

    quality_report = {
        "total_raw": len(raw_tasks),
        "valid": 0,
        "invalid": 0,
        "dates_normalized": 0,
        "dates_failed": 0,
        "courses_unknown": 0,
        "missing_title": 0,
        "missing_course": 0,
        "missing_due_date": 0,
        "task_types": {},
    }

    for raw in raw_tasks:
        # Stage 1 — Whitespace normalization
        title      = raw.get("title", "").strip()
        raw_course = raw.get("course", "").strip()
        raw_date   = raw.get("due_date", "").strip()

        # Stage 2 — Extract task type & clean course name
        task_type    = extract_task_type(raw_course)
        clean_course = clean_course_name(raw_course)

        quality_report["task_types"][task_type] = (
            quality_report["task_types"].get(task_type, 0) + 1
        )
        if clean_course == "Unknown":
            quality_report["courses_unknown"] += 1

        # Stage 3 — Date normalization
        norm_date, date_parsed = normalize_date(raw_date)
        if date_parsed:
            quality_report["dates_normalized"] += 1
        else:
            quality_report["dates_failed"] += 1

        # Stage 4 — Build cleaned record
        cleaned = {
            "title":           title,
            "course":          clean_course,
            "raw_course":      raw_course,
            "task_type":       task_type,
            "due_date":        norm_date,
            "raw_due_date":    raw_date,
            "date_normalized": date_parsed,
        }

        # Stage 5 — Validate
        is_valid, issues = validate_task(cleaned)
        cleaned["is_valid"]          = is_valid
        cleaned["validation_issues"] = issues

        if is_valid:
            quality_report["valid"] += 1
        else:
            quality_report["invalid"] += 1
            for issue in issues:
                if issue in quality_report:
                    quality_report[issue] += 1

        cleaned_tasks.append(cleaned)

    total = max(len(raw_tasks), 1)
    quality_report["completeness_pct"] = round(
        quality_report["valid"] / total * 100, 1
    )

    return cleaned_tasks, quality_report
