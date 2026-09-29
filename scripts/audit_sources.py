"""Probe every configured source and write a factual compatibility snapshot."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sources import contra, freelancer, guru, himalayas, jobicy, peopleperhour, remotive, virtualstaff, wellfound, weworkremotely, detail_jsonld
from sources.common import SourceBlocked
import watcher

SOURCES = {
    'onlinejobsph': lambda http: watcher.fetch_jobs(watcher.JOB_SITES[0]),
    'freelancer': lambda http: freelancer.fetch(http),
    'peopleperhour': lambda http: peopleperhour.fetch(),
    'wellfound': lambda http: wellfound.fetch(detail_limit=10),
    'remotive': lambda http: remotive.fetch(http),
    'contra': lambda http: contra.fetch(),
    'weworkremotely': lambda http: weworkremotely.fetch(http),
    'guru': lambda http: guru.fetch(http),
    'jobicy': lambda http: jobicy.fetch(http),
    'himalayas': lambda http: himalayas.fetch(http),
    'virtualstaff': lambda http: virtualstaff.fetch(),
}


def check(name, fetch):
    http = requests.Session()
    http.headers['User-Agent'] = 'Mozilla/5.0 (compatible; JobWatcher/1.0)'
    result = {'source': name, 'tested_at': datetime.now(timezone.utc).isoformat(), 'status': 'error', 'listing_count': 0, 'detail': 'not tested'}
    try:
        jobs = fetch(http)
        result['listing_count'] = len(jobs)
        result['status'] = 'healthy' if jobs else 'partial'
        fields = ['title', 'url', 'company', 'description', 'posted_at', 'wage_salary', 'type_of_work', 'location', 'skills']
        result['coverage'] = {field: round(sum(bool(job.get(field)) for job in jobs.values()) / len(jobs), 3) if jobs else 0 for field in fields}
        if jobs:
            job_id, job = next(iter(jobs.items()))
            try:
                if name == 'freelancer': detail = freelancer.fetch_detail(http, job['url'])
                elif name == 'onlinejobsph': detail = watcher.fetch_job_detail_onlinejobsph(job['url'])
                elif name == 'virtualstaff': detail = virtualstaff.fetch_detail(job_id)
                elif name in {'jobicy', 'remotive'}: detail = detail_jsonld.fetch_detail(http, job['url'])
                elif name == 'weworkremotely': detail = job
                elif name == 'wellfound': detail = job
                elif name == 'himalayas': detail = job
                else: detail = None
                result['detail'] = 'verified' if detail else 'unavailable'
                if detail:
                    result['detail_fields'] = {field: bool(detail.get(field)) for field in fields}
            except Exception as exc:
                result['detail'] = 'error'
                result['detail_error'] = f'{type(exc).__name__}: {exc}'[:180]
        if result.get('coverage', {}).get('description', 0) < 0.1 and len(jobs) >= 5:
            result['status'] = 'partial'
    except SourceBlocked as exc:
        result['status'] = 'blocked'
        result['error'] = str(exc)[:180]
    except Exception as exc:
        result['status'] = 'error'
        result['error'] = f'{type(exc).__name__}: {exc}'[:180]
    return result


def main():
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(check, name, fetch): name for name, fetch in SOURCES.items()}
        for future in as_completed(futures):
            item = future.result()
            print(item['source'], item['status'], item['listing_count'], item['detail'], flush=True)
            results.append(item)
    Path('data/source_audit.json').write_text(json.dumps(sorted(results, key=lambda item: item['source']), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
