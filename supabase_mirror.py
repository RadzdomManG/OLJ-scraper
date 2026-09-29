"""Mirror the local 5,000-job archive to protected Supabase jobs."""

import hashlib
import json
import os
import threading

import requests

from job_normalizer import normalize_event, TAXONOMY


_lock = threading.Lock()


def configured():
    return bool(os.environ.get('NEXT_PUBLIC_SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_ROLE_KEY'))


def _base():
    return os.environ['NEXT_PUBLIC_SUPABASE_URL'].rstrip('/') + '/rest/v1'


def _headers(prefer='return=minimal'):
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    return {'apikey': key, 'Authorization': 'Bearer ' + key,
            'Content-Type': 'application/json', 'Prefer': prefer}


def _chunks(items, size=40):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def sync_jobs(store, events):
    """Only send changed records; preserve local jobs if cloud sync fails."""
    if not configured() or not _lock.acquire(blocking=False):
        return {'enabled': configured(), 'skipped': True}
    try:
        hashes = store.sync_digests()
        records = [normalize_event(event) for event in events]
        by_key = {record['event_key']: record for record in records}
        changed = []
        for record in records:
            key = record['event_key']
            # last_seen_at changes on every poll, so it is not part of the
            # change digest. The first detection time never changes.
            digest_record = {k: v for k, v in record.items() if k not in ('last_seen_at', 'updated_at')}
            digest = hashlib.sha256(json.dumps(digest_record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if hashes.get(key) != digest:
                changed.append((record, digest))
        sent = 0
        for batch in _chunks(changed):
            response = requests.post(_base() + '/jobs?on_conflict=event_key', headers=_headers('resolution=merge-duplicates,return=minimal'),
                                     json=[item[0] for item in batch], timeout=30)
            response.raise_for_status()
            store.set_sync_digests([(item[0]['event_key'], item[1]) for item in batch])
            sent += len(batch)
        stale = [key for key in hashes if key not in by_key]
        for batch in _chunks(stale):
            response = requests.delete(_base() + '/jobs', headers=_headers(),
                                       params={'event_key': 'in.(' + ','.join('"' + key.replace('"', '\\"') + '"' for key in batch) + ')'}, timeout=30)
            response.raise_for_status()
            store.remove_sync_digests(batch)
        return {'enabled': True, 'upserted': sent, 'pruned': len(stale), 'total': len(records)}
    finally:
        _lock.release()


def sync_taxonomy():
    if not configured():
        return False
    records = [{'id': niche['id'], 'group_name': niche['group'], 'label': niche['label'], 'aliases': niche['aliases']} for niche in TAXONOMY]
    response = requests.post(_base() + '/niche_taxonomy?on_conflict=id',
                             headers=_headers('resolution=merge-duplicates,return=minimal'), json=records, timeout=30)
    response.raise_for_status()
    return True
