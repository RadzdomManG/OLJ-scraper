import { backend, db, owner } from '@/lib/server';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { event_key, stage } = await request.json();
  if (typeof event_key !== 'string' || typeof stage !== 'string') return Response.json({ error: 'Invalid request' }, { status: 400 });
  const response = await backend(`/api/jobs/${encodeURIComponent(event_key)}/stage`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage }) });
  if (response.ok) await db().from('jobs').update({ stage }).eq('event_key', event_key);
  return response;
}
