"""Safely enrich existing local jobs and mirror changed records to Supabase."""

import argparse
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from job_store import JobStore
from job_normalizer import source_posted
from sources import freelancer, virtualstaff, detail_jsonld, himalayas
from supabase_mirror import sync_jobs


def merge(job, detail, source):
    changed = False
    for field in ('description', 'wage_salary', 'type_of_work', 'company', 'category', 'location'):
        value = detail.get(field)
        if value and not job.get(field):
            job[field] = value
            changed = True
    if detail.get('skills') and not job.get('skills'):
        job['skills'] = detail['skills']
        changed = True
    posted = detail.get('posted_at')
    if posted and (not job.get('posted_at') or (source == 'virtualstaff' and source_posted(posted, source))):
        job['posted_at'] = posted
        changed = True
    exact = source_posted(job.get('posted_at'), source)
    if exact and not job.get('posted_at_iso'):
        job['posted_at_iso'] = exact
        changed = True
    if changed:
        job['budget_salary'] = job.get('wage_salary', '')
        job['job_type'] = job.get('type_of_work', '')
        job['detail_checked_at'] = datetime.now(timezone.utc).isoformat()
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Persist enriched records')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / 'frontend/.env.local')
    store = JobStore(str(root / 'data/jobs.sqlite3'))
    events = store.load_jobs()
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; JobWatcher/1.0)'
    counts = Counter()
    api_jobs = {}
    try:
        api_jobs = himalayas.fetch(session)
    except Exception as exc:
        print('Himalayas API unavailable:', type(exc).__name__)
    processed = 0
    for job in events:
        source = job.get('site_type')
        if source not in {'freelancer', 'virtualstaff', 'jobicy', 'remotive', 'himalayas'}:
            continue
        if args.limit and processed >= args.limit:
            break
        if source == 'himalayas':
            detail = api_jobs.get(job.get('job_id'))
            if not detail:
                continue
        else:
            if not job.get('url'):
                continue
            if source != 'virtualstaff' and job.get('wage_salary') and job.get('posted_at_iso') and job.get('type_of_work') and job.get('description'):
                continue
            if source == 'virtualstaff' and job.get('posted_at_iso') and job.get('description'):
                continue
            try:
                if source == 'freelancer':
                    detail = freelancer.fetch_detail(session, job['url'])
                elif source == 'virtualstaff':
                    detail = virtualstaff.fetch_detail(job.get('job_id'))
                else:
                    detail = detail_jsonld.fetch_detail(session, job['url'])
            except Exception as exc:
                counts[f'{source}_errors'] += 1
                print(f'{source} detail failed: {type(exc).__name__}')
                continue
        processed += 1
        if merge(job, detail, source):
            counts[f'{source}_enriched'] += 1
        counts[f'{source}_checked'] += 1
        if args.apply and processed % 20 == 0:
            store.save_jobs(events)
            print('saved progress:', processed)
        if source != 'himalayas':
            time.sleep(random.uniform(0.2, 0.5))
    if args.apply:
        store.save_jobs(events)
        print('mirror:', sync_jobs(store, events))
    print(dict(counts))


if __name__ == '__main__':
    main()
