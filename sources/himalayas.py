"""Himalayas' public RSS feed of recent remote jobs."""

from datetime import datetime, timezone
import time

from .rss_common import CONTENT_NS, field, html_text, iso_date, link_id, rss_items, valid_link


FEED_URL = "https://himalayas.app/jobs/rss"
API_URL = "https://himalayas.app/jobs/api"
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
    """Use the source's public account-free JSON feed for its salary/type fields."""
    jobs = {}
    cursor = None
    for index in range(5):
        params = {'limit': 20}
        if cursor:
            params['cursor'] = cursor
        response = http.get(API_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get('jobs', []):
            job_url = str(item.get('guid') or '')
            if not valid_link(job_url, {"himalayas.app", "www.himalayas.app"}):
                continue
            minimum, maximum = item.get('minSalary'), item.get('maxSalary')
            currency, period = item.get('currency') or '', item.get('salaryPeriod') or ''
            if isinstance(minimum, (int, float)) and minimum > 0:
                wage = f'{currency} {minimum:,.0f}-{maximum:,.0f}/{period}' if isinstance(maximum, (int, float)) and maximum > minimum else f'{currency} {minimum:,.0f}/{period}'
            else:
                wage = ''
            published = item.get('pubDate')
            if isinstance(published, (int, float)):
                published = datetime.fromtimestamp(published / 1000 if published > 1e11 else published, timezone.utc).isoformat()
            locations = item.get('locationRestrictions') or []
            if isinstance(locations, list):
                location = ', '.join(str(place.get('name') if isinstance(place, dict) else place) for place in locations)
            else:
                location = ''
            categories = item.get('categories') or []
            jobs[link_id(job_url)] = {
                'title': str(item.get('title') or '').strip(), 'url': job_url,
                'description': html_text(item.get('description') or item.get('excerpt') or ''),
                'posted_at': str(published or ''), 'type_of_work': str(item.get('employmentType') or ''),
                'wage_salary': wage, 'hours_per_week': '', 'company': str(item.get('companyName') or ''),
                'skills': categories if isinstance(categories, list) else [], 'category': ', '.join((item.get('parentCategories') or [])[:3]),
                'location': location, 'remote': True,
            }
        cursor = payload.get('nextCursor')
        if not cursor:
            break
        time.sleep(0.2)
    return jobs
