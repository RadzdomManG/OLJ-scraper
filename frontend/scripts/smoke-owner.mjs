import nextEnv from '@next/env';
import { createClient } from '@supabase/supabase-js';
import { randomBytes } from 'node:crypto';
import { spawn } from 'node:child_process';

nextEnv.loadEnvConfig(process.cwd());
const db = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
const email = `owner-smoke-${randomBytes(6).toString('hex')}@example.invalid`;
const password = randomBytes(24).toString('base64url');
const base = 'http://localhost:3001';
let userId, codeId, server;
const check = (condition, message) => { if (!condition) throw new Error(message); console.log(`PASS ${message}`); };
async function request(path, options = {}, cookie = '') {
  const response = await fetch(`${base}${path}`, { ...options, headers: { ...(options.headers || {}), ...(cookie ? { cookie } : {}) } });
  let data; try { data = await response.json(); } catch { data = {}; }
  return { response, data };
}
try {
  const created = await db.auth.admin.createUser({ email, password, email_confirm: true });
  if (created.error) throw created.error;
  userId = created.data.user.id;
  server = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '-p', '3001'], { cwd: process.cwd(), env: { ...process.env, OWNER_EMAIL: email }, stdio: 'ignore', windowsHide: true });
  let ready = false;
  for (let retry = 0; retry < 40; retry++) {
    try { if ((await fetch(`${base}/login`)).ok) { ready = true; break; } } catch { /* starting */ }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  check(ready, 'isolated owner portal started');
  const login = await request('/api/auth/owner', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
  check(login.response.status === 200, 'temporary owner signs in');
  const cookie = login.response.headers.get('set-cookie')?.split(';')[0] || '';
  check(cookie.startsWith('aurelius_owner='), 'owner cookie issued');
  check(/Max-Age=34560000/i.test(login.response.headers.get('set-cookie') || ''), 'owner cookie persists across visits');
  check((await request('/api/auth/session', {}, cookie)).response.status === 200, 'owner session renews');
  const add = await request('/api/admin/codes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ label: 'Owner route smoke test', expires_at: new Date(Date.now() + 3600_000).toISOString(), max_uses: 2 }) }, cookie);
  check(add.response.status === 200 && !!add.data.code, 'owner creates membership with expiration');
  codeId = add.data.id;
  const list = await request('/api/admin/codes', {}, cookie);
  check(list.response.status === 200 && list.data.codes.some(code => code.id === codeId), 'owner sees membership');
  check(!JSON.stringify(list.data).includes(add.data.code), 'raw access code is not returned in list');
  const patch = await request('/api/admin/codes', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: codeId, expires_at: new Date(Date.now() + 7200_000).toISOString(), max_uses: 3 }) }, cookie);
  check(patch.response.status === 200, 'owner edits expiration and sign-in limit');
  const revoke = await request('/api/admin/codes', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: codeId, status: 'revoked' }) }, cookie);
  check(revoke.response.status === 200, 'owner revokes membership');
  const reuse = await request('/api/auth/code', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code: add.data.code }) });
  check(reuse.response.status === 401, 'revoked code cannot sign in');
  const deleted = await request('/api/admin/codes', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: codeId }) }, cookie);
  check(deleted.response.status === 200, 'owner deletes membership');
  codeId = undefined;
} finally {
  if (codeId) await db.from('access_codes').delete().eq('id', codeId);
  if (server) server.kill();
  if (userId) await db.auth.admin.deleteUser(userId);
}
