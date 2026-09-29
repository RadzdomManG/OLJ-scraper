"""Extract source-provided JobPosting fields from public detail pages."""

import json
import re

from bs4 import BeautifulSoup


def _job_posting(value):
    if isinstance(value, list):
        return next((part for part in value if isinstance(part, dict) and part.get('@type') == 'JobPosting'), None)
    if isinstance(value, dict):
        if value.get('@type') == 'JobPosting':
            return value
        graph = value.get('@graph')
        if isinstance(graph, list):
            return _job_posting(graph)
    return None


def parse(html):
    soup = BeautifulSoup(html, 'lxml')
    posting = None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            posting = _job_posting(json.loads(tag.string or tag.get_text()))
        except (ValueError, TypeError):
            continue
        if posting:
            break
    if not posting:
        raise ValueError('JobPosting structured data not found')
    salary = posting.get('baseSalary') or {}
    if isinstance(salary, list):
        salary = next((value for value in salary if isinstance(value, dict)), {})
    value = salary.get('value') or {} if isinstance(salary, dict) else {}
    if not isinstance(value, dict):
        value = {'value': value}
    minimum = value.get('minValue', value.get('value'))
    maximum = value.get('maxValue')
    try:
        minimum = float(minimum)
        maximum = float(maximum) if maximum is not None else None
    except (ValueError, TypeError):
        minimum = maximum = None
    currency = str(salary.get('currency') or '').strip() if isinstance(salary, dict) else ''
    period = str(value.get('unitText') or '').strip().lower()
    if minimum and minimum > 0:
        salary_text = f'{currency} {minimum:,.0f}-{maximum:,.0f}/{period}' if maximum and maximum > 0 and maximum != minimum else f'{currency} {minimum:,.0f}/{period}' if period else f'{currency} {minimum:,.0f}'
    else:
        salary_text = ''
    employment = posting.get('employmentType') or ''
    if isinstance(employment, list):
        employment = ', '.join(str(value) for value in employment)
    date = str(posting.get('datePosted') or '').strip()
    if date.endswith(' UTC'):
        date = date[:-4].replace(' ', 'T', 1) + '+00:00'
    if not re.search(r'(Z|[+-]\d\d:?\d\d)$', date):
        date = ''
    organization = posting.get('hiringOrganization') or {}
    if not isinstance(organization, dict):
        organization = {}
    skills = posting.get('skills') or []
    if isinstance(skills, str):
        skills = [x.strip() for x in skills.split(',') if x.strip()]
    if not isinstance(skills, list):
        skills = []
    return {
        'posted_at': date, 'wage_salary': salary_text,
        'type_of_work': str(employment).replace('_', ' ').strip().title(),
        'description': BeautifulSoup(str(posting.get('description') or ''), 'lxml').get_text(' ', strip=True),
        'company': str(organization.get('name') or '').strip(),
        'skills': skills, 'category': str(posting.get('occupationalCategory') or '').strip(),
    }


def fetch_detail(http, url, timeout=15):
    response = http.get(url, timeout=timeout)
    response.raise_for_status()
    return parse(response.text)
