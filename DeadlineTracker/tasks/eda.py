"""
Exploratory Data Analysis (EDA) + Visualization — Phase 1 Rubric (10 + 5 pts)

Call run_full_eda() to:
  1. Compute descriptive statistics from the database
  2. Generate matplotlib charts saved as PNG files
  3. Return a JSON-serialisable summary dict

Charts produced (saved to media/eda/):
  - tasks_per_course.png
  - completion_status.png
  - task_types.png
  - tasks_per_day.png
"""

import os
import json
from collections import Counter
from datetime import datetime

# ── Django ORM import guard ───────────────────────────────────────────────────
try:
    from .models import UniversityTask
    _DJANGO_AVAILABLE = True
except Exception:
    _DJANGO_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Statistics helpers (work on a list of task dicts or ORM objects)
# ─────────────────────────────────────────────────────────────────────────────

def _get_tasks_as_dicts():
    """Fetch all tasks from the database as plain dicts."""
    tasks = []
    for t in UniversityTask.objects.select_related("user").all():
        tasks.append({
            "id":           t.id,
            "title":        t.title,
            "course":       t.course,
            "due_date":     t.due_date,
            "created_at":   t.created_at,
            "is_completed": t.is_completed,
            "user":         t.user.username if t.user else "anonymous",
        })
    return tasks


def compute_statistics(tasks: list) -> dict:
    """
    Compute descriptive statistics over a list of task dicts.

    Returns a dict suitable for JSON serialisation.
    """
    total = len(tasks)
    if total == 0:
        return {"error": "No tasks found in database."}

    completed = sum(1 for t in tasks if t["is_completed"])
    pending   = total - completed

    # Course distribution
    course_counts  = Counter(t["course"] for t in tasks)
    top_courses    = course_counts.most_common(10)

    # Task type distribution (extracted from raw course prefix, if available)
    # If course was already cleaned, approximate by counting unique prefixes
    from .preprocessing import TASK_TYPE_PREFIXES, extract_task_type
    # Re-use raw_course if present, else approximate
    type_counter = Counter()
    for t in tasks:
        raw = t.get("raw_course", t["course"])
        type_counter[extract_task_type(raw)] += 1

    # User workload
    user_counts = Counter(t["user"] for t in tasks)
    task_counts_per_user = list(user_counts.values())
    avg_per_user = round(sum(task_counts_per_user) / max(len(task_counts_per_user), 1), 1)

    # Deadline distribution (parse due_date where possible)
    due_dates_parsed = []
    for t in tasks:
        raw = t["due_date"]
        for fmt in ["%Y-%m-%d %H:%M:%S", "%A, %d %B %Y - %H:%M", "%d %B %Y - %H:%M"]:
            try:
                due_dates_parsed.append(datetime.strptime(raw, fmt))
                break
            except ValueError:
                continue

    # Day-of-week breakdown
    day_counts = Counter(d.strftime("%A") for d in due_dates_parsed)

    stats = {
        "total_tasks":         total,
        "total_users":         len(user_counts),
        "completed":           completed,
        "pending":             pending,
        "completion_rate_pct": round(completed / total * 100, 1),
        "top_courses":         [{"course": c, "count": n} for c, n in top_courses],
        "task_types":          dict(type_counter),
        "avg_tasks_per_user":  avg_per_user,
        "max_tasks_per_user":  max(task_counts_per_user, default=0),
        "min_tasks_per_user":  min(task_counts_per_user, default=0),
        "deadlines_by_weekday": dict(day_counts),
        "unique_courses":      len(course_counts),
    }
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Visualisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def generate_charts(stats: dict, output_dir: str = "media/eda") -> list:
    """
    Generate and save all EDA charts as PNG files.

    Returns a list of saved file paths.
    """
    import matplotlib
    matplotlib.use("Agg")        # headless — no display needed
    import matplotlib.pyplot as plt

    _ensure_dir(output_dir)
    saved = []

    BLUE   = "#4A9EFF"
    TEAL   = "#00D4AA"
    ORANGE = "#F39C12"
    GREEN  = "#27AE60"
    RED    = "#E74C3C"
    BG     = "#0D1117"
    TEXT   = "#C9D1D9"
    GRID   = "#21262D"

    def _style_ax(ax, title):
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT, labelsize=9)
        ax.title.set_color(TEXT)
        ax.set_title(title, fontsize=12, pad=10)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.yaxis.grid(True, color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)

    # ── Chart 1: Tasks per Course (top 8) ────────────────────────────────────
    if stats.get("top_courses"):
        labels  = [c["course"][:25] for c in stats["top_courses"][:8]]
        values  = [c["count"]       for c in stats["top_courses"][:8]]
        colors  = [BLUE if i % 2 == 0 else TEAL for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(9, 4.5))
        fig.patch.set_facecolor(BG)
        bars = ax.bar(labels, values, color=colors, edgecolor="none", width=0.6)
        ax.bar_label(bars, padding=3, color=TEXT, fontsize=9)
        _style_ax(ax, "Tasks per Course (Top 8)")
        plt.xticks(rotation=30, ha="right", fontsize=8)
        plt.tight_layout()
        path = os.path.join(output_dir, "tasks_per_course.png")
        plt.savefig(path, dpi=120, bbox_inches="tight", facecolor=BG)
        plt.close()
        saved.append(path)

    # ── Chart 2: Completion Status (Pie) ─────────────────────────────────────
    completed = stats.get("completed", 0)
    pending   = stats.get("pending",   0)
    if completed + pending > 0:
        fig, ax = plt.subplots(figsize=(5, 5))
        fig.patch.set_facecolor(BG)
        wedge_colors = [ORANGE, GREEN]
        wedges, texts, autotexts = ax.pie(
            [pending, completed],
            labels=["Pending", "Completed"],
            colors=wedge_colors,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"color": TEXT, "fontsize": 11},
        )
        for at in autotexts:
            at.set_color(BG)
            at.set_fontsize(10)
        _style_ax(ax, "Task Completion Status")
        ax.set_aspect("equal")
        path = os.path.join(output_dir, "completion_status.png")
        plt.savefig(path, dpi=120, bbox_inches="tight", facecolor=BG)
        plt.close()
        saved.append(path)

    # ── Chart 3: Task Types (horizontal bar) ─────────────────────────────────
    if stats.get("task_types"):
        tt     = stats["task_types"]
        labels = list(tt.keys())
        values = list(tt.values())
        type_colors = [BLUE, TEAL, RED, ORANGE, GREEN][: len(labels)]

        fig, ax = plt.subplots(figsize=(7, max(2.5, len(labels) * 0.7)))
        fig.patch.set_facecolor(BG)
        bars = ax.barh(labels, values, color=type_colors, edgecolor="none", height=0.5)
        ax.bar_label(bars, padding=4, color=TEXT, fontsize=9)
        _style_ax(ax, "Task Types Distribution")
        ax.xaxis.grid(True, color=GRID, linewidth=0.5)
        ax.yaxis.grid(False)
        plt.tight_layout()
        path = os.path.join(output_dir, "task_types.png")
        plt.savefig(path, dpi=120, bbox_inches="tight", facecolor=BG)
        plt.close()
        saved.append(path)

    # ── Chart 4: Deadlines by Day of Week ────────────────────────────────────
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_data   = stats.get("deadlines_by_weekday", {})
    if day_data:
        ordered_values = [day_data.get(d, 0) for d in days_order]
        day_colors     = [BLUE if v > 0 else GRID for v in ordered_values]

        fig, ax = plt.subplots(figsize=(8, 4))
        fig.patch.set_facecolor(BG)
        bars = ax.bar(days_order, ordered_values, color=day_colors, edgecolor="none", width=0.55)
        ax.bar_label(bars, padding=3, color=TEXT, fontsize=9)
        _style_ax(ax, "Deadline Distribution by Day of Week")
        plt.tight_layout()
        path = os.path.join(output_dir, "tasks_per_day.png")
        plt.savefig(path, dpi=120, bbox_inches="tight", facecolor=BG)
        plt.close()
        saved.append(path)

    return saved


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_full_eda(output_dir: str = "media/eda", report_path: str = "media/eda/eda_report.json") -> dict:
    """
    Run the complete EDA pipeline:
      1. Fetch tasks from the database
      2. Compute statistics
      3. Generate and save charts
      4. Write JSON report

    Returns the statistics dict.
    """
    tasks = _get_tasks_as_dicts()
    stats = compute_statistics(tasks)

    if "error" in stats:
        return stats

    charts = generate_charts(stats, output_dir=output_dir)
    stats["charts_saved"] = charts

    # Write JSON report
    _ensure_dir(os.path.dirname(report_path) or ".")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2, default=str)

    return stats
