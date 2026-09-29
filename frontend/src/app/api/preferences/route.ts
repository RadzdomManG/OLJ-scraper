import { db, owner, viewer } from '@/lib/server';
import { NICHES, validNicheIds } from '@/lib/customer-match';
import { NextRequest } from 'next/server';

export async function GET() {
  if (await owner()) return Response.json({ error: 'Customer settings only' }, { status: 403 });
  const member = await viewer();
  if (!member) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { data, error } = await db().from('viewer_preferences').select('niches').eq('code_id', member.id).maybeSingle();
  if (error) return Response.json({ error: 'Unable to load preferences' }, { status: 500 });
  return Response.json({ niches: NICHES.map(({ id, label, group }) => ({ id, label, group })), selected: data ? { niches: data.niches } : null }, { headers: { 'Cache-Control': 'no-store' } });
}

export async function PUT(request: NextRequest) {
  if (await owner()) return Response.json({ error: 'Customer settings only' }, { status: 403 });
  const member = await viewer();
  if (!member) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  let body: unknown;
  try { body = await request.json(); } catch { return Response.json({ error: 'Invalid request' }, { status: 400 }); }
  if (!body || typeof body !== 'object') return Response.json({ error: 'Invalid request' }, { status: 400 });
  const { niches } = body as Record<string, unknown>;
  if (!Array.isArray(niches) || niches.length > 20 ||
    !niches.every(id => typeof id === 'string' && validNicheIds.has(id)))
    return Response.json({ error: 'Choose valid niches' }, { status: 400 });
  const selectedNiches = [...new Set(niches as string[])];
  if (!selectedNiches.length) return Response.json({ error: 'Choose at least one niche' }, { status: 400 });
  const { error } = await db().from('viewer_preferences').upsert({ code_id: member.id, niches: selectedNiches, keywords: [], updated_at: new Date().toISOString() });
  return error ? Response.json({ error: 'Unable to save preferences' }, { status: 500 }) : Response.json({ ok: true });
}
