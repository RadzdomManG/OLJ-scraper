import { codeHash, db, newCode, owner } from '@/lib/server';
import { NextRequest } from 'next/server';
export async function GET() {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { data, error } = await db().from('access_codes').select('id,label,status,expires_at,max_uses,used_count,created_at,created_by,last_used_at').order('created_at', { ascending: false });
  return error ? Response.json({ error: error.message }, { status: 500 }) : Response.json({ codes: data });
}
export async function POST(request: NextRequest) {
  const user = await owner(); if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const body = await request.json(); const code = newCode();
  const label = String(body.label || '').trim(); const max = body.max_uses === '' || body.max_uses == null ? null : Number(body.max_uses);
  const expires = body.expires_at ? new Date(body.expires_at) : null;
  if (!label || label.length > 100 || (max !== null && (!Number.isInteger(max) || max < 1)) || (expires && (isNaN(expires.getTime()) || expires <= new Date()))) return Response.json({ error: 'Check label, expiration and max uses' }, { status: 400 });
  const { data, error } = await db().from('access_codes').insert({ code_hash: codeHash(code), label, expires_at: expires?.toISOString() || null, max_uses: max, created_by: user.id }).select('id').single();
  return error ? Response.json({ error: error.message }, { status: 500 }) : Response.json({ id: data.id, code });
}
export async function PATCH(request: NextRequest) {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { id, status, expires_at, max_uses } = await request.json();
  if (typeof id !== 'string' || !/^[0-9a-f-]{36}$/i.test(id)) return Response.json({ error: 'Invalid membership' }, { status: 400 });
  const updates: Record<string, unknown> = {};
  if (status !== undefined) {
    if (status !== 'active' && status !== 'revoked') return Response.json({ error: 'Invalid status' }, { status: 400 });
    updates.status = status;
  }
  if (expires_at !== undefined) {
    const date = expires_at ? new Date(expires_at) : null;
    if (date && (Number.isNaN(date.getTime()) || date <= new Date())) return Response.json({ error: 'Expiration must be in the future' }, { status: 400 });
    updates.expires_at = date?.toISOString() || null;
  }
  if (max_uses !== undefined) {
    const max = max_uses === null || max_uses === '' ? null : Number(max_uses);
    if (max !== null && (!Number.isInteger(max) || max < 1)) return Response.json({ error: 'Invalid maximum sign-ins' }, { status: 400 });
    updates.max_uses = max;
  }
  if (!Object.keys(updates).length) return Response.json({ error: 'No changes supplied' }, { status: 400 });
  const { error } = await db().from('access_codes').update(updates).eq('id', id);
  return error ? Response.json({ error: error.message }, { status: 500 }) : Response.json({ ok: true });
}
export async function DELETE(request: NextRequest) {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { id } = await request.json(); const { error } = await db().from('access_codes').delete().eq('id', id);
  return error ? Response.json({ error: error.message }, { status: 500 }) : Response.json({ ok: true });
}
