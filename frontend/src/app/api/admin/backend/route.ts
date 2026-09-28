import { backend, owner } from '@/lib/server';
import { NextRequest } from 'next/server';
export async function GET(request: NextRequest) { if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 }); const kind = request.nextUrl.searchParams.get('kind'); return backend(kind === 'analytics' ? '/api/analytics' : '/api/status'); }
export async function POST() { if (!await owner()) return Response.json({ error: 'Unauthorized' }, { status: 401 }); return backend('/api/control/scan-now', { method: 'POST' }); }
