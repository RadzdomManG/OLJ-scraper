import { createClient } from '@supabase/supabase-js';
import { cookies } from 'next/headers';
import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';

export type CodeRecord = { id: string; code_hash: string; label: string; status: string; expires_at: string | null; max_uses: number | null; used_count: number; created_at: string; created_by: string | null; last_used_at: string | null };

export function db() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error('Supabase server configuration is missing');
  return createClient(url, key, { auth: { persistSession: false } });
}

function sign(value: string) {
  const secret = process.env.SESSION_SECRET;
  if (!secret) throw new Error('SESSION_SECRET is missing');
  return createHmac('sha256', secret).update(value).digest('hex');
}

export function codeHash(code: string) { return sign(`code:${code.trim().toUpperCase()}`); }
export function newCode() { return `AUR-${randomBytes(9).toString('hex').toUpperCase()}`; }
export function sessionValue(id: string) { return `${id}.${sign(`session:${id}`)}`; }

export async function viewer() {
  const value = (await cookies()).get('aurelius_code')?.value;
  if (!value) return null;
  const separator = value.lastIndexOf('.');
  if (separator < 0) return null;
  const id = value.slice(0, separator);
  const signature = value.slice(separator + 1);
  const expected = sign(`session:${id}`);
  if (signature.length !== expected.length || !timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) return null;
  const { data } = await db().from('access_codes').select('*').eq('id', id).maybeSingle<CodeRecord>();
  if (!data || data.status !== 'active' || (data.expires_at && new Date(data.expires_at) <= new Date())) return null;
  return data;
}

export async function owner() {
  const token = (await cookies()).get('aurelius_owner')?.value;
  if (!token) return null;
  const { data, error } = await db().auth.getUser(token);
  if (error || !data.user || data.user.email?.toLowerCase() !== process.env.OWNER_EMAIL?.toLowerCase()) return null;
  return data.user;
}

export async function backend(path: string, init?: RequestInit) {
  const base = process.env.NEXT_PUBLIC_BACKEND_API_URL;
  if (!base) return Response.json({ error: 'Backend URL is not configured' }, { status: 503 });
  try {
    const response = await fetch(`${base.replace(/\/$/, '')}${path}`, {
      ...init,
      headers: { 'X-Backend-Token': process.env.BACKEND_API_TOKEN || '', ...init?.headers },
      cache: 'no-store',
      signal: AbortSignal.timeout(12000),
    });
    return new Response(await response.text(), { status: response.status, headers: { 'Content-Type': response.headers.get('Content-Type') || 'application/json', 'Cache-Control': 'no-store' } });
  } catch {
    return Response.json({ error: 'Backend offline' }, { status: 503 });
  }
}
