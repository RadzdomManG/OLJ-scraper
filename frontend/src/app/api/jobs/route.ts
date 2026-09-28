import { backend, owner, viewer } from '@/lib/server';
export async function GET() { if (!await owner() && !await viewer()) return Response.json({ error: 'Unauthorized' }, { status: 401 }); return backend('/api/jobs?limit=500'); }
