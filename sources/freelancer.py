import hashlib
import random
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

SEARCH_URLS = (
    "https://www.freelancer.com/jobs/",
)


def fetch(http, urls=SEARCH_URLS, timeout=12):
    jobs = {}
    for index, url in enumerate(urls):
        if index:
            time.sleep(random.uniform(0.4, 1.0))
        response = http.get(url, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "lxml")
        cards = soup.select("div.JobSearchCard-item")
        if not cards:
            raise ValueError(f"Freelancer listing layout changed: {url}")
        for card in cards:
            link = card.select_one("a.JobSearchCard-primary-heading-link[href]")
            if not link:
                continue
            full_url = urljoin("https://www.freelancer.com", link["href"])
            path = urlparse(full_url).path.rstrip("/")
            if not path.startswith("/projects/"):
                continue
            title = link.get_text(" ", strip=True)
            description_tag = card.select_one("p.JobSearchCard-primary-description")
            description = description_tag.get_text(" ", strip=True) if description_tag else ""
            tags = [tag.get_text(" ", strip=True) for tag in card.select("a.JobSearchCard-primary-tagsLink")]
            job_id = hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]
            jobs[job_id] = {
                "title": title, "url": full_url, "description": description,
                "posted_at": "", "type_of_work": "", "wage_salary": "", "hours_per_week": "",
                "company": "", "skills": tags, "location": "", "remote": None,
            }
    return jobs


def fetch_detail(http, url, timeout=12):
    """Use the public project page; listing 'average bid' is not the budget."""
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'lxml')
    heading = soup.select_one('div.Project-heading-title')
    if not heading:
        raise ValueError('Freelancer project detail layout changed')
    budget = heading.select_one('h2')
    description = soup.select_one('p.Project-description')
    posted = heading.select_one('fl-relative-time')
    payment = heading.select_one('div.mobile\\:hide p') or heading.select_one('p.text-right')
    return {
        'wage_salary': budget.get_text(' ', strip=True) if budget else '',
        'description': description.get_text(' ', strip=True) if description else '',
        'posted_at': posted.get_text(' ', strip=True) if posted else '',
        'type_of_work': payment.get_text(' ', strip=True) if payment else '',
    }
