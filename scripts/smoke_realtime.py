"""Three-customer all-jobs visibility and Supabase Realtime delivery check."""

import hashlib
import hmac
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from job_normalizer import normalize_event

load_dotenv(root / 'frontend/.env.local')
base = os.environ.get('SMOKE_BASE_URL', 'http://localhost:3000')
url = os.environ['NEXT_PUBLIC_SUPABASE_URL'].rstrip('/') + '/rest/v1'
key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
headers = {'apikey': key, 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
created_codes = []
created_jobs = []
run_id = secrets.token_hex(5)


def api(method, table, payload=None, params=None):
    response = requests.request(method, f'{url}/{table}', headers=headers, json=payload, params=params, timeout=20)
    response.raise_for_status()
    return response.json() if response.content else None


def membership(label, niche):
    code = 'AUR-TEST-' + secrets.token_hex(8).upper()
    digest = hmac.new(os.environ['SESSION_SECRET'].encode(), f'code:{code}'.encode(), hashlib.sha256).hexdigest()
    member = api('POST', 'access_codes', {'label': label, 'code_hash': digest})[0]
    created_codes.append(member['id'])
    api('POST', 'viewer_preferences', {'code_id': member['id'], 'niches': [niche], 'keywords': []})
    return code


def make_job(name, title, description):
    event = {'event_key': f'smoke:{run_id}:{name}', 'site_type': 'smoke', 'job_id': name,
             'url': f'https://example.invalid/jobs/{run_id}/{name}', 'title': title,
             'description': description, 'detected_at': datetime.now(timezone.utc).isoformat()}
    job = normalize_event(event)
    created_jobs.append(job['event_key'])
    return job


try:
    profiles = [('A', 'virtual-assistant'), ('B', 'video-editor'), ('C', 'comfyui')]
    codes = {name: membership('Temporary realtime test ' + name, niche) for name, niche in profiles}
    seed = [make_job('va-one', 'Virtual Assistant', 'General VA scheduling and inbox support'),
            make_job('video-one', 'Video Editing Specialist', 'Reels editor and CapCut editor'),
            make_job('ai-one', 'ComfyUI Workflow Developer', 'ComfyUI custom nodes and image generation'),
            make_job('accounting-one', 'Accounting Clerk', 'Bookkeeping and payroll')]
    api('POST', 'jobs', seed)
    assert seed[0]['primary_niche'] == 'virtual-assistant'
    assert 'video-editor' in seed[1]['niches']
    assert 'comfyui' in seed[2]['niches']
    assert seed[3]['niches'] == []
    print('PASS classifier maps VA, Video, ComfyUI and excludes Accounting')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        pages = {}
        for name, _ in profiles:
            context = browser.new_context()
            page = context.new_page()
            page.goto(f'{base}/login')
            page.get_by_label('Access code', exact=True).fill(codes[name])
            page.get_by_role('button', name='Continue').click()
            page.wait_for_url('**/jobs')
            page.get_by_text('Jobs', exact=True).first.wait_for()
            pages[name] = page
        expected = ['Virtual Assistant', 'Video Editing Specialist', 'ComfyUI Workflow Developer', 'Accounting Clerk']
        for page in pages.values():
            for title in expected:
                page.locator('tbody').get_by_text(title, exact=True).first.wait_for(timeout=15000)
        print('PASS customer A/B/C see all jobs, including unmatched Accounting')
        # The status becomes Live only after Supabase confirms SUBSCRIBED.
        for page in pages.values():
            page.get_by_text('Live', exact=True).first.wait_for(timeout=20000)
        inserted_at = datetime.now(timezone.utc)
        next_job = make_job('va-two', 'Virtual Assistant Realtime Test', 'General VA and administrative VA')
        api('POST', 'jobs', [next_job])
        for page in pages.values():
            page.locator('tbody').get_by_text('Virtual Assistant Realtime Test', exact=True).first.wait_for(timeout=15000)
        received_at = datetime.now(timezone.utc)
        assert 'PERFECT MATCH' in pages['A'].locator('tbody tr').filter(has_text='Virtual Assistant Realtime Test').inner_text()
        for name in ('B', 'C'):
            assert 'General listing' in pages[name].locator('tbody tr').filter(has_text='Virtual Assistant Realtime Test').inner_text()
        print('PASS realtime insert without refresh; inserted_at=', inserted_at.isoformat(), 'received_at=', received_at.isoformat(), 'delay_seconds=', round((received_at - inserted_at).total_seconds(), 2))
        browser.close()
finally:
    for event_key in created_jobs:
        api('DELETE', 'jobs', params={'event_key': 'eq.' + event_key})
    for member_id in created_codes:
        api('DELETE', 'access_codes', params={'id': 'eq.' + member_id})
