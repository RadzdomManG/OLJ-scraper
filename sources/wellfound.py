import json
import random
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .common import SourceBlocked


LIST_URL = "https://wellfound.com/jobs"


def parse_job_posting(html, url):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            record = json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError):
            continue
        if isinstance(record, list):
            record = next((part for part in record if part.get("@type") == "JobPosting"), {})
        if record.get("@type") != "JobPosting":
            continue
        title = str(record.get("title") or "").strip()
        description = BeautifulSoup(str(record.get("description") or ""), "lxml").get_text(" ", strip=True)
        identifier = record.get("identifier") or {}
        job_id = str(identifier.get("value") or "").strip()
        if not job_id:
            match = re.search(r"/jobs/(\d+)", url)
            job_id = match.group(1) if match else ""
        if not job_id:
            return None
        salary = record.get("baseSalary") or {}
        salary_value = salary.get("value") or {}
        if isinstance(salary_value, dict):
            low, high = salary_value.get("minValue"), salary_value.get("maxValue")
            salary_text = f"{salary.get('currency', '')} {low:g}–{high:g} / {salary_value.get('unitText', '').lower()}" if isinstance(low, (int, float)) and isinstance(high, (int, float)) else ""
        else:
            salary_text = ""
        organization = record.get("hiringOrganization") or {}
        locations = record.get("jobLocation") or []
        if isinstance(locations, dict):
            locations = [locations]
        places = []
        for place in locations:
            address = place.get("address") or {}
            if isinstance(address, dict):
                label = ", ".join(str(address.get(key) or "").strip() for key in ("addressLocality", "addressRegion", "addressCountry"))
                label = ", ".join(part for part in label.split(", ") if part)
                if label:
                    places.append(label)
        return job_id, {
            "title": title, "url": url, "description": description,
            "posted_at": str(record.get("datePosted") or "").strip(),
            "type_of_work": str(record.get("employmentType") or "").replace("_", " ").title(),
            "wage_salary": salary_text, "hours_per_week": "",
            "company": str(organization.get("name") or "").strip(), "skills": [],
            "location": "; ".join(places),
            "remote": record.get("jobLocationType") == "TELECOMMUTE" or None,
        }
    return None


def fetch(timeout_ms=15000, detail_limit=50):
    from playwright.sync_api import sync_playwright

    jobs = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(LIST_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            if not response or response.status >= 400:
                raise SourceBlocked(f"Wellfound public list returned {response.status if response else 'no response'}")
            soup = BeautifulSoup(page.content(), "lxml")
            candidates = []
            for link in soup.select('a[href^="/jobs/"]'):
                title = link.get_text(" ", strip=True)
                href = link.get("href", "")
                if title and re.match(r"^/jobs/\d+", href):
                    candidates.append(urljoin(LIST_URL, href))
            if not candidates and "one more step" in soup.get_text(" ", strip=True).lower():
                raise SourceBlocked("Wellfound returned a security challenge")
            for url in dict.fromkeys(candidates[:detail_limit]):
                time.sleep(random.uniform(0.3, 0.8))
                response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                if not response or response.status >= 400 or urlparse(page.url).path.startswith("/login"):
                    continue
                parsed = parse_job_posting(page.content(), url)
                if parsed:
                    job_id, job = parsed
                    jobs[job_id] = job
        finally:
            browser.close()
    return jobs
