"""
Data Storage & Export Module — Phase 1 Rubric (10 pts)

Provides:
  - export_to_json()  → structured JSON dataset
  - export_to_xml()   → structured XML dataset
"""

import json
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

from .models import UniversityTask


def _queryset(user=None):
    qs = UniversityTask.objects.select_related("user").all()
    if user is not None:
        qs = qs.filter(user=user)
    return qs


def _task_to_dict(task) -> dict:
    return {
        "id":           task.id,
        "title":        task.title,
        "course":       task.course,
        "due_date":     task.due_date,
        "created_at":   task.created_at.isoformat(),
        "is_completed": task.is_completed,
        "user":         task.user.username if task.user else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# JSON Export
# ─────────────────────────────────────────────────────────────────────────────

def export_to_json(filepath: str = "dataset_export.json", user=None) -> tuple:
    """
    Export all tasks (or a single user's tasks) to a structured JSON file.

    Returns:
        (filepath, record_count)
    """
    qs = _queryset(user)
    tasks_data = [_task_to_dict(t) for t in qs]

    export_data = {
        "metadata": {
            "project":      "DeadlineTracker",
            "source":       "MSA University E-Learning Platform (Moodle)",
            "source_url":   "https://e-learning.msa.edu.eg",
            "exported_at":  datetime.now().isoformat(),
            "total_records": len(tasks_data),
            "schema_version": "1.0",
        },
        "tasks": tasks_data,
    }

    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    return filepath, len(tasks_data)


# ─────────────────────────────────────────────────────────────────────────────
# XML Export
# ─────────────────────────────────────────────────────────────────────────────

def export_to_xml(filepath: str = "dataset_export.xml", user=None) -> tuple:
    """
    Export all tasks (or a single user's tasks) to a structured XML file.

    Returns:
        (filepath, record_count)
    """
    qs = _queryset(user)

    root = ET.Element("DeadlineTrackerDataset")

    meta = ET.SubElement(root, "metadata")
    ET.SubElement(meta, "project").text      = "DeadlineTracker"
    ET.SubElement(meta, "source").text       = "MSA University E-Learning Platform"
    ET.SubElement(meta, "source_url").text   = "https://e-learning.msa.edu.eg"
    ET.SubElement(meta, "exported_at").text  = datetime.now().isoformat()
    ET.SubElement(meta, "total_records").text = str(qs.count())

    tasks_el = ET.SubElement(root, "tasks")
    count = 0
    for task in qs:
        t = ET.SubElement(tasks_el, "task")
        ET.SubElement(t, "id").text           = str(task.id)
        ET.SubElement(t, "title").text        = task.title
        ET.SubElement(t, "course").text       = task.course
        ET.SubElement(t, "due_date").text     = task.due_date
        ET.SubElement(t, "created_at").text   = task.created_at.isoformat()
        ET.SubElement(t, "is_completed").text = str(task.is_completed).lower()
        ET.SubElement(t, "user").text         = task.user.username if task.user else ""
        count += 1

    xmlstr = minidom.parseString(
        ET.tostring(root, encoding="unicode")
    ).toprettyxml(indent="  ")

    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(xmlstr)

    return filepath, count
