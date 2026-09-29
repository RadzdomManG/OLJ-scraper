import { backend, owner } from '@/lib/server';
import { NextRequest } from 'next/server';

export async function GET() {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  return backend('/api/match-settings');
}

export async function POST(request: NextRequest) {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  return backend('/api/match-settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: await request.text() });
}
