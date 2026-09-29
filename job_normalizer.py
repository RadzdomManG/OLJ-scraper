"""Source-preserving job normalization and conservative niche classification."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


TAXONOMY = json.loads((Path(__file__).parent / 'frontend/src/lib/niches.json').read_text(encoding='utf-8'))
NICHES_BY_ID = {entry['id']: entry for entry in TAXONOMY}
PHT = ZoneInfo('Asia/Manila')
PARENTS = {
    'executive-assistant': 'virtual-assistant', 'administrative-assistant': 'virtual-assistant',
    'ecommerce-va': 'virtual-assistant', 'real-estate-va': 'virtual-assistant',
    'short-form-video': 'video-editor',
    'ai-image': 'generative-ai', 'ai-video': 'generative-ai', 'comfyui': 'generative-ai',
    'lora': 'generative-ai', 'ai-engineer': 'generative-ai', 'ai-automation': 'generative-ai',
    'openai': 'generative-ai', 'workflow-automation': 'ai-automation',
    'fullstack-developer': 'frontend-developer',
}


def normalized(value):
    return ' ' + re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower())).strip() + ' '


def matching_aliases(text, aliases):
    return [alias for alias in aliases if normalized(alias) in text]


def classify(job):
    title = normalized(job.get('title'))
    description = normalized(job.get('description'))
    metadata = normalized(' '.join(str(x) for x in [*(job.get('skills') or []), *(job.get('tags') or []), job.get('category') or '']))
    results = {}
    for niche in TAXONOMY:
        aliases = niche['aliases']
        if matching_aliases(title + description + metadata, niche.get('exclude', [])):
            continue
        title_hits = matching_aliases(title, aliases)
        metadata_hits = matching_aliases(metadata, aliases)
        description_hits = matching_aliases(description, aliases)
        unique_hits = set(title_hits + metadata_hits + description_hits)
        # One mention deep in a description is too weak to classify a job.
        if title_hits:
            score = 100 if metadata_hits or len(unique_hits) >= 2 else 85
        elif metadata_hits and description_hits:
            score = 80
        elif metadata_hits:
            score = 75
        elif len(unique_hits) >= 2:
            score = 65
        else:
            continue
        results[niche['id']] = {'score': score, 'terms': sorted(unique_hits)[:8]}
    for child, parent in PARENTS.items():
        if child in results and parent not in results:
            results[parent] = {'score': max(60, results[child]['score'] - 15), 'terms': results[child]['terms']}
    order = sorted(results, key=lambda key: (-results[key]['score'], key))
    return {'primary_niche': order[0] if order else None, 'niches': order,
            'niche_scores': {key: results[key]['score'] for key in order},
            'normalized_tags': sorted({term for item in results.values() for term in item['terms']})[:30]}


def source_posted(value, source):
    """Return UTC only when the source supplied an exact clock time."""
    raw = str(value or '').strip()
    if not raw or re.search(r'\b(today|yesterday|ago|just now)\b', raw, re.I):
        return None
    if not re.search(r'\d{1,2}:\d{2}', raw):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = datetime.strptime(raw, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return None
    if parsed.tzinfo is None:
        if source != 'onlinejobsph':
            return None
        parsed = parsed.replace(tzinfo=PHT)
    return parsed.astimezone(timezone.utc).isoformat()


def salary_parts(raw):
    value = str(raw or '').strip()
    if not value:
        return {'salary_raw': None, 'salary_min': None, 'salary_max': None, 'salary_currency': None, 'salary_period': None}
    currency_match = re.search(r'\b(USD|PHP|GBP|EUR|AUD|CAD|NZD|INR|SGD)\b', value, re.I)
    currency = currency_match.group(1).upper() if currency_match else 'PHP' if '₱' in value or 'â‚±' in value else 'USD' if '$' in value else 'GBP' if '£' in value else 'EUR' if '€' in value else None
    amounts = [float(x.replace(',', '')) for x in re.findall(r'(?<![\w])\d[\d,]*(?:\.\d+)?', value)[:2]]
    period = next((period for pattern, period in [
        (r'\b(hour|hourly|hr)\b', 'hour'), (r'\b(day|daily)\b', 'day'),
        (r'\b(week|weekly)\b', 'week'), (r'\b(month|monthly|mo)\b', 'month'),
        (r'\b(year|annual|annually)\b', 'year'), (r'\b(project|fixed)\b', 'project')
    ] if re.search(pattern, value, re.I)), None)
    return {'salary_raw': value, 'salary_min': amounts[0] if amounts else None,
            'salary_max': amounts[1] if len(amounts) > 1 else None,
            'salary_currency': currency, 'salary_period': period}


def work_type(value):
    raw = str(value or '').strip()
    text = normalized(raw)
    for phrase, label in [('full time', 'Full-time'), ('part time', 'Part-time'), ('contract', 'Contract'),
                          ('freelance', 'Freelance'), ('temporary', 'Temporary'), ('hourly', 'Hourly'),
                          ('paid on delivery', 'Project'),
                          ('fixed price', 'Fixed price'), ('project', 'Project')]:
        if normalized(phrase) in text:
            return label
    return raw or None


def normalize_event(event):
    source = event.get('site_type', '')
    posted_raw = event.get('posted_at') or None
    detected = event.get('detected_at') or datetime.now(timezone.utc).isoformat()
    classification = classify(event)
    salary = salary_parts(event.get('wage_salary'))
    return {
        'event_key': event['event_key'], 'source': source, 'source_job_id': str(event.get('job_id') or ''),
        'source_url': event.get('url') or None, 'title': event.get('title') or '',
        'company': event.get('company') or None, 'description': event.get('description') or None,
        'skills': event.get('skills') or [], 'location': event.get('location') or None,
        'category': event.get('category') or None, 'tags': event.get('tags') or [],
        'source_posted_raw': posted_raw,
        'source_posted_at': source_posted(event.get('posted_at_iso') or posted_raw, source),
        'first_seen_at': detected, 'last_seen_at': event.get('last_seen_at') or detected,
        'work_type_raw': event.get('type_of_work') or None, 'work_type': work_type(event.get('type_of_work')),
        **salary, **classification,
        'detail_checked_at': event.get('detail_checked_at') or None,
        'quality_flags': [],
        'notification_sent': bool(event.get('notification_sent')),
        'owner_score': event.get('job_score'), 'owner_priority': event.get('priority') or None,
    }
