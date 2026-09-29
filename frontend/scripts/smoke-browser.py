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
        page = browser.new_page()
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
        assert page.get_by_label('Source').is_visible()
        assert page.get_by_role('link', name='My niche').is_visible()
        assert not page.get_by_role('link', name='Access Codes').count()
        page.get_by_role('button', name='Load more jobs').click()
        page.wait_for_timeout(1200)
        assert not page.get_by_role('button', name='Next page').count()
        page.get_by_role('link', name='My niche').click()
        assert page.get_by_label('Virtual Assistant', exact=True).is_checked()
        print('PASS customer onboarding, persistent niche, job list and load more')
        browser.close()
finally:
    requests.delete(f'{supabase}/rest/v1/access_codes?id=eq.{member_id}', headers=headers, timeout=15).raise_for_status()
