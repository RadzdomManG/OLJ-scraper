import { backend, owner } from '@/lib/server';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest) {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { event_key, stage } = await request.json();
  if (typeof event_key !== 'string' || typeof stage !== 'string') return Response.json({ error: 'Invalid request' }, { status: 400 });
  return backend(`/api/jobs/${encodeURIComponent(event_key)}/stage`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage }) });
}
