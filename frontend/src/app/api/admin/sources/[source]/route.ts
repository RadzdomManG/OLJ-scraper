import { backend, owner } from '@/lib/server';
import { NextRequest } from 'next/server';

export async function POST(request: NextRequest, context: { params: Promise<{ source: string }> }) {
  if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const { source } = await context.params;
  const body = await request.text();
  return backend(`/api/sources/${encodeURIComponent(source)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
}
