"""Local customer browser check. Uses a temporary membership and removes it."""
import hashlib
import hmac
import os
import secrets
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

for line in Path('.env.local').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        os.environ.setdefault(key, value.strip().strip('"'))

base = os.environ.get('SMOKE_BASE_URL', 'http://localhost:3000')
supabase = os.environ['NEXT_PUBLIC_SUPABASE_URL'].rstrip('/')
key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
headers = {'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Prefer': 'return=representation'}
code = 'AUR-TEST-' + secrets.token_hex(8).upper()
code_hash = hmac.new(os.environ['SESSION_SECRET'].encode(), f'code:{code}'.encode(), hashlib.sha256).hexdigest()
record = requests.post(f'{supabase}/rest/v1/access_codes', headers=headers, json={'label': 'Temporary browser smoke test', 'code_hash': code_hash}, timeout=15)
record.raise_for_status()
member_id = record.json()[0]['id']

try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        page.goto(f'{base}/login')
        page.get_by_label('Access code', exact=True).fill(code)
        page.get_by_role('button', name='Continue').click()
        page.wait_for_url('**/preferences')
        assert page.get_by_text('Choose your niche').is_visible()
        page.get_by_label('Virtual Assistant', exact=True).wait_for()
        page.get_by_label('Virtual Assistant', exact=True).check()
        page.get_by_role('button', name='Save and view jobs').click()
        page.wait_for_url('**/jobs')
        page.get_by_text('Jobs', exact=True).first.wait_for()
        page.get_by_role('button', name='Load more jobs').wait_for(timeout=15000)
        posted_cell = page.locator('tbody tr').first.locator('td').nth(3).inner_text()
        assert 'PHT' in posted_cell or 'N/A' in posted_cell or 'Exact time unavailable' in posted_cell, posted_cell
        assert page.get_by_text('Aurelius', exact=True).first.is_visible()
        screenshot_dir = Path('../data/runtime_check')
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_dir / 'customer-jobs-desktop.png'), full_page=False)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(screenshot_dir / 'customer-jobs-mobile.png'), full_page=False)
        page.set_viewport_size({'width': 1600, 'height': 900})
        assert not page.get_by_label('Source').count()
        for filter_label in ('Niche', 'Date', 'Work type', 'Minimum salary', 'Salary currency', 'Salary period', 'Match priority'):
            assert not page.get_by_label(filter_label, exact=True).count(), filter_label
        assert page.get_by_placeholder('Search titles or keywords...').is_visible()
        assert not page.get_by_text('OLJ', exact=True).count()
        assert page.get_by_role('link', name='My niche').is_visible()
        assert not page.get_by_role('link', name='Access Codes').count()
        page.get_by_role('button', name='Load more jobs').click()
        page.wait_for_timeout(1200)
        assert not page.get_by_role('button', name='Next page').count()
        with page.expect_response(lambda response: '/api/jobs?' in response.url and 'sort=priority' in response.url, timeout=30000) as priority_response:
            page.get_by_label('Sort jobs').select_option('priority')
        priority_jobs = priority_response.value.json()['jobs']
        scores = [job['match_score'] for job in priority_jobs]
        assert scores == sorted(scores, reverse=True), scores[:10]
        next_priority = page.request.get(f'{base}/api/jobs?sort=priority&offset=100')
        assert next_priority.ok, next_priority.status
        next_scores = [job['match_score'] for job in next_priority.json()['jobs']]
        assert not next_scores or scores[-1] >= next_scores[0], (scores[-1], next_scores[0])
        with page.expect_response(lambda response: '/api/jobs?' in response.url and 'q=ComfyUI' in response.url, timeout=30000) as search_response:
            page.get_by_label('Search titles or keywords').fill('ComfyUI')
        search_data = search_response.value.json()
        assert search_data['total'] > 0, search_data
        assert all('comfyui' in (str(job.get('title', '')) + str(job.get('description', ''))).lower() for job in search_data['jobs'])
        page.get_by_label('Search titles or keywords').fill('')
        page.get_by_role('link', name='My niche').click()
        assert page.get_by_label('Virtual Assistant', exact=True).is_checked()
        print('PASS customer onboarding, priority sort, keyword search, job list and load more')
        browser.close()
finally:
    requests.delete(f'{supabase}/rest/v1/access_codes?id=eq.{member_id}', headers=headers, timeout=15).raise_for_status()
