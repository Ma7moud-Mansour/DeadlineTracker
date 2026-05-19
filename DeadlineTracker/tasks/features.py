"""
Feature Extraction Module — Phase 2 (15 pts)

Extracts from task data:
  1. TF-IDF representation of task titles
  2. Urgency score  (0–100, higher = more urgent)
  3. Urgency label  (overdue / urgent / soon / upcoming / future)
  4. Keyword extraction from task titles
  5. Workload index per course
"""

import math
import re
from collections import Counter, defaultdict
from datetime import datetime

# ── Stop-words (English + Arabic) ────────────────────────────────────────────
STOP_WORDS = {
    # English
    "the","a","an","of","in","for","on","with","to","and","or","is","are",
    "was","were","be","been","have","has","had","do","does","did","will",
    "would","could","should","may","might","must","from","by","at","this",
    "that","its","not","quiz","assignment","lab","homework","project","exam",
    "final","mid","due","submit","deadline","upload","report","activity","part",
    # Arabic
    "في","من","على","إلى","عن","مع","هذا","هذه","التي","الذي","لا","لم",
    "هو","هي","نحن","أنت","أنا","كان","كانت","يكون","تكون",
}

# ── Date formats Moodle uses ──────────────────────────────────────────────────
_DATE_FMTS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%A, %d %B %Y - %H:%M", "%d %B %Y - %H:%M",
    "%A, %d %B %Y", "%d %B %Y",
]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _days_remaining(due_date_str: str) -> float:
    """Return days until deadline (negative = overdue). 9999 if unparseable."""
    for fmt in _DATE_FMTS:
        try:
            dt = datetime.strptime(due_date_str.strip(), fmt)
            return (dt - datetime.now()).total_seconds() / 86400
        except (ValueError, AttributeError):
            continue
    return 9999.0


def _tokenize(text: str) -> list:
    tokens = re.findall(r"[a-zA-Z؀-ۿ]{3,}", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Urgency scoring & classification
# ─────────────────────────────────────────────────────────────────────────────

def compute_urgency_score(due_date_str: str) -> float:
    """
    Urgency score 0.0 – 100.0.
      100  = already overdue
      80+  = due today
      50+  = due within 7 days
      0    = 30+ days away
    """
    days = _days_remaining(due_date_str)
    if days <= 0:
        return 100.0
    if days <= 1:
        return round(80 + (1 - days) * 20, 1)
    if days <= 7:
        return round(50 + (7 - days) / 6 * 30, 1)
    if days <= 30:
        return round((30 - days) / 23 * 50, 1)
    return 0.0


def classify_urgency(due_date_str: str) -> str:
    """Return urgency label: overdue / urgent / soon / upcoming / future."""
    days = _days_remaining(due_date_str)
    if days <= 0:   return "overdue"
    if days <= 3:   return "urgent"
    if days <= 7:   return "soon"
    if days <= 30:  return "upcoming"
    return "future"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Keyword extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_keywords(text: str, top_n: int = 5) -> list:
    """Extract top_n keywords from a text string (frequency-based after stop-word removal)."""
    tokens = _tokenize(text)
    if not tokens:
        return []
    counts = Counter(tokens)
    return [word for word, _ in counts.most_common(top_n)]


# ─────────────────────────────────────────────────────────────────────────────
# 3. TF-IDF
# ─────────────────────────────────────────────────────────────────────────────

def compute_tfidf(tasks: list) -> dict:
    """
    Compute TF-IDF scores for all task titles.

    Args:
        tasks : list of task dicts (each must have a 'title' key)

    Returns:
        dict  {task_index: {term: tfidf_score, ...}}
    """
    docs = [_tokenize(t.get("title", "")) for t in tasks]
    N = len(docs)
    if N == 0:
        return {}

    # Document frequency  (how many docs contain each term)
    df = Counter()
    for doc in docs:
        df.update(set(doc))

    result = {}
    for i, doc in enumerate(docs):
        if not doc:
            result[i] = {}
            continue
        tf = Counter(doc)
        total = len(doc)
        scores = {
            term: round((cnt / total) * (math.log((N + 1) / (df[term] + 1)) + 1), 4)
            for term, cnt in tf.items()
        }
        # Keep top 5 terms per task
        result[i] = dict(sorted(scores.items(), key=lambda x: -x[1])[:5])

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. Workload index per course
# ─────────────────────────────────────────────────────────────────────────────

def compute_workload_index(tasks: list) -> dict:
    """
    Compute workload index per course.
    Combines task count with weighted urgency to rank course load.

    Returns:
        {course: {count, urgency_sum, workload_index}}  sorted by workload desc
    """
    data = defaultdict(lambda: {"count": 0, "urgency_sum": 0.0})
    for t in tasks:
        course = t.get("course", "Unknown") or "Unknown"
        data[course]["count"]       += 1
        data[course]["urgency_sum"] += compute_urgency_score(t.get("due_date", ""))

    result = {}
    for course, vals in data.items():
        result[course] = {
            "count":          vals["count"],
            "urgency_sum":    round(vals["urgency_sum"], 1),
            "workload_index": round(vals["urgency_sum"] / max(vals["count"], 1), 1),
        }

    return dict(sorted(result.items(), key=lambda x: -x[1]["workload_index"]))


# ─────────────────────────────────────────────────────────────────────────────
# 5. TF-IDF keyword search
# ─────────────────────────────────────────────────────────────────────────────

def search_tasks(tasks: list, query: str, top_n: int = 10) -> list:
    """
    Rank tasks by relevance to a search query using cosine similarity over TF-IDF.

    Returns list of (task_index, score) sorted by relevance.
    """
    if not query.strip() or not tasks:
        return []

    # Build TF-IDF for task corpus
    tfidf = compute_tfidf(tasks)
    query_tokens = set(_tokenize(query))

    results = []
    for i, scores in tfidf.items():
        # Simple dot-product with query terms
        relevance = sum(scores.get(tok, 0.0) for tok in query_tokens)
        # Fallback: substring match in title
        title_lower = tasks[i].get("title", "").lower()
        if any(tok in title_lower for tok in query_tokens):
            relevance = max(relevance, 0.1)
        if relevance > 0:
            results.append((i, round(relevance, 4)))

    return sorted(results, key=lambda x: -x[1])[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# 6. Enrich all tasks with features
# ─────────────────────────────────────────────────────────────────────────────

def enrich_tasks(tasks: list) -> list:
    """
    Add urgency_score, urgency_label, and keywords to every task dict.
    Operates in-place and returns the list.
    """
    for t in tasks:
        t["urgency_score"] = compute_urgency_score(t.get("due_date", ""))
        t["urgency_label"] = classify_urgency(t.get("due_date", ""))
        t["keywords"]      = extract_keywords(t.get("title", ""))
    return tasks
