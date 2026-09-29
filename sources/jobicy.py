"""Jobicy's public RSS feed, checked no more than once per hour."""

from .rss_common import CONTENT_NS, field, html_text, iso_date, link_id, rss_items, valid_link


FEED_URL = "https://jobicy.com/jobs/feed"
NS = "{https://jobicy.com}"


def parse(content):
    jobs = {}
    for item in rss_items(content):
        title, url = field(item, "title"), field(item, "link")
        if not title or not valid_link(url, {"jobicy.com", "www.jobicy.com"}):
            continue
        job_id = field(item, "id") or link_id(url)
        category = field(item, NS + "category")
        jobs[job_id] = {
            "title": title,
            "url": url,
            "description": html_text(field(item, CONTENT_NS) or field(item, "description")),
            "posted_at": iso_date(field(item, "pubDate")),
            "type_of_work": field(item, NS + "job_type"),
            "wage_salary": field(item, NS + "salary"),
            "hours_per_week": "",
            "company": field(item, NS + "company"),
            "skills": [category] if category else [],
            "location": field(item, NS + "location"),
            "remote": True,
        }
    return jobs


def fetch(http, url=FEED_URL, timeout=20):
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return parse(response.content)
