"""Himalayas' public RSS feed of recent remote jobs."""

from .rss_common import CONTENT_NS, field, html_text, iso_date, link_id, rss_items, valid_link


FEED_URL = "https://himalayas.app/jobs/rss"
NS = "{https://himalayas.app/ns/jobs}"


def parse(content):
    jobs = {}
    for item in rss_items(content):
        title, url = field(item, "title"), field(item, "link")
        if not title or not valid_link(url, {"himalayas.app", "www.himalayas.app"}):
            continue
        categories = [node.text.strip() for node in item.findall("category") if node.text and node.text.strip()]
        jobs[link_id(url)] = {
            "title": title,
            "url": url,
            "description": html_text(field(item, CONTENT_NS) or field(item, "description")),
            "posted_at": iso_date(field(item, "pubDate")),
            "type_of_work": "",
            "wage_salary": "",
            "hours_per_week": "",
            "company": field(item, NS + "companyName"),
            "skills": categories,
            "location": field(item, NS + "locationRestriction"),
            "remote": True,
        }
    return jobs


def fetch(http, url=FEED_URL, timeout=20):
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return parse(response.content)
