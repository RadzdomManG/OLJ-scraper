import nextEnv from '@next/env';
import { createClient } from '@supabase/supabase-js';
import { createHmac, randomBytes } from 'node:crypto';

nextEnv.loadEnvConfig(process.cwd());
const db = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
const base = process.env.SMOKE_BASE_URL || 'http://localhost:3000';
const code = `AUR-TEST-${randomBytes(8).toString('hex')}`;
const code_hash = createHmac('sha256', process.env.SESSION_SECRET).update(`code:${code.toUpperCase()}`).digest('hex');
let id;
const check = (condition, message) => { if (!condition) throw new Error(message); console.log(`PASS ${message}`); };
async function request(path, options = {}, cookie = '') {
  const response = await fetch(`${base}${path}`, { ...options, headers: { ...(options.headers || {}), ...(cookie ? { cookie } : {}) }, redirect: 'manual' });
  let data;
  try { data = await response.json(); } catch { data = {}; }
  return { response, data };
}
try {
  const inserted = await db.from('access_codes').insert({ label: 'Temporary smoke test', code_hash, max_uses: 2, expires_at: new Date(Date.now() + 3600_000).toISOString() }).select('id').single();
  if (inserted.error) throw inserted.error;
  id = inserted.data.id;
  check((await request('/api/jobs')).response.status === 401, 'anonymous jobs blocked');
  check((await request('/api/preferences')).response.status === 401, 'anonymous preferences blocked');
  check((await request('/api/admin/codes')).response.status === 401, 'customer code admin blocked');
  const signin = await request('/api/auth/code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
  check(signin.response.status === 200, 'valid membership signs in');
  const cookie = signin.response.headers.get('set-cookie')?.split(';')[0] || '';
  check(cookie.startsWith('aurelius_code='), 'session cookie issued');
  check(/Max-Age=34560000/i.test(signin.response.headers.get('set-cookie') || ''), 'customer cookie persists across visits');
  check((await request('/api/jobs', {}, cookie)).response.status === 409, 'profile required before jobs');
  const put = await request('/api/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ niches: ['comfyui'] }) }, cookie);
  check(put.response.status === 200, 'customer can save niche without resending code');
  const preferences = await request('/api/preferences', {}, cookie);
  check(preferences.data.selected?.niches?.includes('comfyui'), 'niche persists');
  check((await request('/api/auth/session', {}, cookie)).response.status === 200, 'customer session renews without another code use');
  check((await request('/api/admin/codes', {}, cookie)).response.status === 401, 'customer cannot list access codes');
  check((await request('/api/jobs/stage', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_key: 'test', stage: 'saved' }) }, cookie)).response.status === 401, 'customer cannot change owner stages');
  const jobs = await request('/api/jobs', {}, cookie);
  check(jobs.response.status === 200, 'customer receives live jobs');
  check(jobs.data.jobs?.length > 0, 'customer sees stored jobs');
  const archive = await db.from('jobs').select('event_key', { count: 'exact', head: true });
  if (archive.error) throw archive.error;
  check(jobs.data.total === archive.count, 'customer sees the full archive regardless of niche');
  check(jobs.data.jobs.some(job => job.match_score === 0), 'unmatched jobs remain visible');
  const ignoredFilters = await request('/api/jobs?priority=perfect&niche=virtual-assistant&salary_min=999999&source=contra', {}, cookie);
  check(ignoredFilters.data.total === archive.count, 'customer request cannot hide jobs with extra filters');
  const first = jobs.data.jobs[0];
  check(!['site', 'site_type', 'source', 'event_key', 'matched_keywords', 'notification_sent', 'job_id', 'source_posted_raw', 'source_posted_at'].some(key => Object.hasOwn(first, key)), 'customer response excludes source and owner internals');
  check(typeof first.match_score === 'number', 'customer jobs include personal match score');
  const second = await request('/api/auth/code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
  check(second.response.status === 200, 'second permitted sign in works');
  check((await request('/api/auth/code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) })).response.status === 401, 'maximum sign-ins enforced');
  const expiry = await db.from('access_codes').update({ expires_at: new Date(Date.now() - 1000).toISOString() }).eq('id', id);
  if (expiry.error) throw expiry.error;
  check((await request('/api/preferences', {}, cookie)).response.status === 401, 'expired membership loses access immediately');
  check((await request('/api/auth/session', {}, cookie)).response.status === 401, 'expired membership is forced out');
} finally {
  if (id) await db.from('access_codes').delete().eq('id', id);
}
