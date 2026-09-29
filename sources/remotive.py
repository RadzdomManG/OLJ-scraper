from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .common import is_generation_job


API_URL = "https://remotive.com/api/remote-jobs"


def fetch(http, url=API_URL, timeout=20):
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload.get("jobs"), list):
        raise ValueError("Remotive response has no jobs list")
    jobs = {}
    for item in payload["jobs"]:
        title = str(item.get("title") or "").strip()
        description = BeautifulSoup(str(item.get("description") or ""), "lxml").get_text(" ", strip=True)
        if not title or not is_generation_job(title, description):
            continue
        job_id = str(item.get("id") or "").strip()
        url = str(item.get("url") or "").strip()
        if not job_id or urlparse(url).hostname not in {"remotive.com", "www.remotive.com"}:
            continue
        jobs[job_id] = {
            "title": title, "url": url, "description": description,
            "posted_at": str(item.get("publication_date") or "").strip(),
            "type_of_work": str(item.get("job_type") or "").replace("_", " ").strip(),
            "wage_salary": str(item.get("salary") or "").strip(), "hours_per_week": "",
            "company": str(item.get("company_name") or "").strip(),
            "skills": [], "location": str(item.get("candidate_required_location") or "").strip(),
            "remote": True,
        }
    return jobs
