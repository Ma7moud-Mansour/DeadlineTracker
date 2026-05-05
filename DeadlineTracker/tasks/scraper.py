"""
MSA Moodle Scraper — Phase 1

Ethical crawling:
  - robots.txt is checked before any scraping begins
  - Only the authenticated user's own data is accessed
  - Sequential page loads with implicit waits (no parallel hammering)
  - "Load More" button clicked up to MAX_LOAD_MORE times for full coverage
"""

import time
import urllib.robotparser

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from .preprocessing import preprocess_tasks

BASE_URL      = "https://e-learning.msa.edu.eg"
LOGIN_URL     = f"{BASE_URL}/login/index.php"
DASHBOARD_URL = f"{BASE_URL}/my/"
ROBOTS_URL    = f"{BASE_URL}/robots.txt"
MAX_LOAD_MORE = 5   # maximum "Load More" clicks to avoid infinite loops


# ─────────────────────────────────────────────────────────────────────────────
# Robots.txt compliance
# ─────────────────────────────────────────────────────────────────────────────

def _is_scraping_allowed(url: str, user_agent: str = "*") -> bool:
    """Return True if robots.txt permits fetching url for the given user_agent."""
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(ROBOTS_URL)
    try:
        rp.read()
    except Exception:
        # If we can't read robots.txt, default to allowed (fail-open)
        return True
    return rp.can_fetch(user_agent, url)


# ─────────────────────────────────────────────────────────────────────────────
# Main scraper
# ─────────────────────────────────────────────────────────────────────────────

def run_msa_scraper(student_id: str, student_password: str):
    """
    Log in to MSA Moodle as the student and extract all upcoming tasks.

    Returns:
        (True,  list_of_cleaned_task_dicts)  on success
        (False, error_message_str)           on failure
    """
    # ── Robots.txt check ─────────────────────────────────────────────────────
    if not _is_scraping_allowed(DASHBOARD_URL):
        return False, "Scraping disallowed by robots.txt"

    driver = None
    try:
        # ── Headless Chrome setup ─────────────────────────────────────────────
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)

        # ── Login ─────────────────────────────────────────────────────────────
        driver.get(LOGIN_URL)
        driver.find_element(By.ID, "username").send_keys(student_id)
        driver.find_element(By.ID, "password").send_keys(student_password)
        driver.find_element(By.ID, "loginbtn").click()

        time.sleep(3)

        if "login" in driver.current_url:
            return False, "بيانات الدخول غلط يا هندسة، اتأكد من الـ ID والباسورد بتوع المودل."

        # ── Navigate to timeline dashboard ────────────────────────────────────
        driver.get(DASHBOARD_URL)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-region='event-list-item']")
            )
        )

        # ── Click "Load More" up to MAX_LOAD_MORE times ───────────────────────
        for _ in range(MAX_LOAD_MORE):
            try:
                load_more = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "[data-action='more-events']")
                    )
                )
                # Scroll into view first, then JS-click to bypass any overlay
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", load_more)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", load_more)
                time.sleep(1.5)
            except TimeoutException:
                break   # no more button — all tasks loaded

        # ── Extract raw task data ─────────────────────────────────────────────
        # Re-fetch by index on every iteration to avoid StaleElementReferenceException
        # (Moodle re-renders the DOM after each "Load More" click)
        raw_tasks = []
        task_count = len(driver.find_elements(
            By.CSS_SELECTOR, "[data-region='event-list-item']"
        ))

        for i in range(task_count):
            try:
                # Always re-query the full list so each reference is fresh
                tasks_live = driver.find_elements(
                    By.CSS_SELECTOR, "[data-region='event-list-item']"
                )
                if i >= len(tasks_live):
                    break
                task = tasks_live[i]

                title = task.find_element(
                    By.CSS_SELECTOR, ".event-name a"
                ).text.strip()

                course_info = task.find_element(
                    By.CSS_SELECTOR, ".event-name-container small"
                ).text.strip()

                due_time = task.find_element(
                    By.CSS_SELECTOR, ".timeline-name small.text-end"
                ).text.strip()

                date_header = task.find_element(
                    By.XPATH,
                    "./ancestor::div[contains(@class,'list-group')]"
                    "/preceding-sibling::div[@data-region='event-list-content-date'][1]"
                ).text.strip()

                raw_tasks.append({
                    "title":    title,
                    "course":   course_info,
                    "due_date": f"{date_header} - {due_time}",
                })
            except (StaleElementReferenceException, NoSuchElementException, Exception):
                continue

        # ── Preprocess (clean + validate) ─────────────────────────────────────
        cleaned_tasks, _quality_report = preprocess_tasks(raw_tasks)

        # Return only valid tasks mapped to the fields the view expects
        result = [
            {
                "title":    t["title"],
                "course":   t["course"],
                "due_date": t["due_date"],
            }
            for t in cleaned_tasks
            if t.get("is_valid", True)
        ]

        return True, result

    except Exception as e:
        return False, str(e)

    finally:
        if driver:
            driver.quit()
