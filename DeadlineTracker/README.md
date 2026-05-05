# DeadlineTracker

**CS313 — Information Retrieval · Phase 1 · MSA University · Spring 2026**

An automated academic task tracker that scrapes MSA University's Moodle e-learning platform and displays all deadlines in a unified dashboard.

---

## Team

| Name | ID |
|------|----|
| Omar Hesham | 247469 |
| Mahmoud Abdelkareem | 247519 |
| Noureen Mohamed | 246173 |
| Ahmed Ebrahim | 246057 |
| Mohamed Sayed | 246861 |

---

## Project Domain

**Domain:** EdTech / Academic Task Intelligence

**Problem:** Students enrolled in 7+ Moodle courses struggle to track scattered assignment deadlines, leading to missed submissions.

**Solution:** A credential-based Selenium scraper that logs into MSA's Moodle, extracts every upcoming task across all enrolled courses, and presents them in a searchable deadline dashboard.

---

## System Architecture

```
Moodle (https://e-learning.msa.edu.eg)
        │
        ▼
[1] Web Scraping       — Selenium 4.43 + headless Chrome (scraper.py)
        │
        ▼
[2] Data Preprocessing — Clean course names, normalize dates (preprocessing.py)
        │
        ▼
[3] Data Storage       — SQLite via Django ORM + JSON/XML export (export.py)
        │
        ▼
[4] EDA & Visualization — Statistics + matplotlib charts (eda.py)
        │
        ▼
[5] Dashboard UI       — Django 5.2 + HTML/CSS deadline tracker
```

---

## Features

### Web Scraping (`tasks/scraper.py`)
- Headless Chrome via Selenium 4.43
- Credential-based authentication (student's own MSA account)
- **robots.txt compliance** — checked before any request via `urllib.robotparser`
- **"Load More" pagination** — clicks up to 5 times to capture all upcoming tasks
- Integrated preprocessing pipeline runs automatically after extraction

### Data Preprocessing (`tasks/preprocessing.py`)
Pipeline stages:
1. Whitespace normalization
2. Task-type prefix extraction (Assignment, Quiz, Turnitin, etc.)
3. Date string normalization → ISO 8601 format
4. Field validation (title, course, due_date)
5. Quality report generation

Supported Moodle date formats:
- `Wednesday, 15 April 2026 - 12:45`
- `15 April 2026 - 12:45`
- `Wednesday, 15 April 2026`
- `15 April 2026`

### Data Storage (`tasks/export.py`)
- **SQLite** — primary operational database via Django ORM
- **JSON export** — structured dataset with metadata (`/export/json/`)
- **XML export** — structured dataset for interoperability (`/export/xml/`)
- Unique constraint on `(user, title, course)` prevents duplicate insertion

### Data Quality Handling (`tasks/models.py`, `tasks/preprocessing.py`)
- **Duplicates** — blocked at the ORM level with `get_or_create`
- **Missing data** — invalid records flagged, not silently dropped
- **Noisy course names** — Moodle prefix codes stripped automatically
- **Date parsing failures** — tracked in quality report, original value preserved

### EDA & Visualization (`tasks/eda.py`)
Statistics computed:
- Total tasks, users, completed/pending counts, completion rate
- Course distribution (top 10)
- Task type distribution
- Deadline distribution by day of week
- Per-user workload (avg/min/max)

Charts generated (saved to `media/eda/`):
- `tasks_per_course.png` — bar chart of top 8 courses
- `completion_status.png` — pie chart of completed vs pending
- `task_types.png` — horizontal bar chart of task types
- `tasks_per_day.png` — deadline distribution by weekday

---

## Setup

### Requirements
```
Python 3.11+
Google Chrome + ChromeDriver (auto-managed by webdriver-manager)
```

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run migrations
```bash
python manage.py migrate
```

### Start the server
```bash
python manage.py runserver
```

### Run EDA pipeline
```bash
python manage.py run_eda
```

---

## API Endpoints

| URL | Description |
|-----|-------------|
| `/` | Login / Sync form |
| `/dashboard/` | Task deadline dashboard |
| `/complete-task/<id>/` | Mark task complete (POST) |
| `/export/json/` | Download tasks as JSON |
| `/export/xml/` | Download tasks as XML |
| `/eda/` | Run EDA and return statistics JSON |
| `/logout/` | Log out |

---

## Dataset

Extracted dataset: `extracted_data.json`

- **167 tasks** from **76 MSA students**
- **10 unique courses** across CS, Math, and Soft Skills
- **34 completed** (20.4%), **133 pending** (79.6%)
- Top course: Principle of Information Systems — 44 tasks

---

## Ethical Crawling

- Robots.txt is read and respected before any scraping
- Users authenticate with their own MSA credentials — no anonymous bulk crawling
- Only the authenticated student's personal academic data is accessed
- Sequential page loads with implicit waits — minimal server load

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.2 |
| Scraping | Selenium 4.43 + WebDriverManager |
| Database | SQLite (Django ORM) |
| Charts | matplotlib 3.7+ |
| Export | JSON + XML (stdlib) |
| Frontend | HTML + CSS + JavaScript |

---

## Repository

https://github.com/Ma7moud-Mansour/DeadlineTracker
