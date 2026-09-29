"""Public Guru freelance project listing."""

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


LIST_URL = "https://www.guru.com/d/jobs/"


def parse(html):
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.jobRecord[data-gid]")
    if not cards:
        raise ValueError("Guru's public job cards were not found")
    jobs = {}
    for card in cards:
        link = card.select_one("h2.jobRecord__title a[href]")
        if not link:
            continue
        raw_url = urljoin(LIST_URL, link["href"])
        parsed = urlparse(raw_url)
        if parsed.hostname not in {"guru.com", "www.guru.com"} or not parsed.path.startswith("/jobs/"):
            continue
        url = raw_url.split("&SearchUrl=", 1)[0]
        job_id = str(card.get("data-gid") or "").strip()
        if not job_id:
            continue
        budget = card.select_one("div.jobRecord__budget")
        budget_parts = [x.get_text(" ", strip=True) for x in budget.select("strong")] if budget else []
        meta = card.select_one("div.jobRecord__meta strong")
        description = card.select_one("p.jobRecord__desc")
        client = card.select_one("h3.identityName")
        location = card.select_one("p.freelancerAvatar__subText")
        jobs[job_id] = {
            "title": link.get_text(" ", strip=True),
            "url": url,
            "description": description.get_text(" ", strip=True) if description else "",
            "posted_at": meta.get_text(" ", strip=True) if meta else "",
            "type_of_work": budget_parts[0] if budget_parts else "",
            "wage_salary": budget_parts[1] if len(budget_parts) > 1 else "",
            "hours_per_week": "",
            "company": client.get_text(" ", strip=True) if client else "",
            "skills": [tag.get_text(" ", strip=True) for tag in card.select(".skillsList__skill")],
            "location": location.get_text(" ", strip=True) if location else "",
            "remote": None,
        }
    return jobs


def fetch(http, url=LIST_URL, timeout=20):
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return parse(response.text)
