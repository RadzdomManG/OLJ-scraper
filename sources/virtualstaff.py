"""VirtualStaff.ph's browser-visible public jobs page."""

import re
import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .common import SourceBlocked


LIST_URL = "https://www.virtualstaff.ph/en-ph/find-jobs"


def parse(html):
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select('a[href^="/jobs-in-philippines/"]')
    if not cards:
        raise ValueError("VirtualStaff public job cards were not found")
    jobs = {}
    for card in cards:
        url = urljoin(LIST_URL, card.get("href", ""))
        parts = urlparse(url).path.split("/")
        if len(parts) < 4 or not re.fullmatch(r"[0-9a-f]{16,32}", parts[2]):
            continue
        title = card.select_one("h6")
        if not title:
            continue
        posted = card.select_one("div.text-right div")
        work_type = card.select_one("button")
        salary = card.select_one("span.text-sm")
        paragraphs = card.select("p")
        description = paragraphs[-1].get_text(" ", strip=True).removesuffix("know More").strip() if paragraphs else ""
        if description == "...":
            description = ""
        jobs[parts[2]] = {
            "title": title.get_text(" ", strip=True), "url": url,
            "description": description,
            "posted_at": posted.get_text(" ", strip=True) if posted else "",
            "type_of_work": work_type.get_text(" ", strip=True) if work_type else "",
            "wage_salary": salary.get_text(" ", strip=True) if salary else "",
            "hours_per_week": "", "company": "", "skills": [],
            "location": "Philippines", "remote": True,
        }
    return jobs


def fetch(timeout_ms=20000):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(LIST_URL, wait_until="networkidle", timeout=timeout_ms)
            if not response or response.status >= 400 or "/login" in page.url:
                raise SourceBlocked(f"VirtualStaff public list returned {response.status if response else 'no response'}")
            return parse(page.content())
        finally:
            browser.close()


def fetch_detail(job_id, timeout=15):
    """Read the same public job detail response used by the source website."""
    response = requests.post('https://www.virtualstaff.ph/api/external/individual-job', json={'id': str(job_id)}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    item = payload.get('result') if payload.get('status') else None
    if not isinstance(item, dict) or str(item.get('_id')) != str(job_id):
        raise ValueError('VirtualStaff detail response did not match the job')
    if item.get('is_deleted') or item.get('is_expired'):
        return {'expired': True}
    description = str(item.get('description') or item.get('job_description') or '').strip()
    if not description and isinstance(item.get('questionnaire'), list):
        details = []
        for entry in item['questionnaire']:
            question = str(entry.get('question') or '').strip()
            answer = entry.get('answer')
            answer = ', '.join(str(value) for value in answer) if isinstance(answer, list) else str(answer or '').strip()
            if question and answer:
                details.append(f'{question}\n{answer}')
        description = '\n\n'.join(details)
    amount = item.get('monthly_salary_php')
    salary = f'₱{amount:,.0f}/month' if isinstance(amount, (int, float)) and amount > 0 else ''
    return {
        'description': description,
        'posted_at': str(item.get('created_time') or '').strip(),
        'wage_salary': salary,
        'type_of_work': str(item.get('job_type') or '').replace('_', ' ').title(),
        'company': str(item.get('created_by') or '').strip(),
        'skills': [str(skill.get('name') or skill.get('skill') or '').strip() for skill in item.get('skills', []) if isinstance(skill, dict)],
        'expired': False,
    }
