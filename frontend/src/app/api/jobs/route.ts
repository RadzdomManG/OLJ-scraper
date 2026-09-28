import { backend, owner, viewer } from '@/lib/server';
import { NextRequest } from 'next/server';
export async function GET(request: NextRequest) {
  if (!await owner() && !await viewer()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const params = new URLSearchParams();
  params.set('limit', '100');
  for (const key of ['offset', 'q', 'keyword', 'status']) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) params.set(key, value.slice(0, 200));
  }
  const response = await backend(`/api/jobs?${params.toString()}`);
  if (!response.ok) return response;
  const data = await response.json();
  const jobs = (Array.isArray(data.jobs) ? data.jobs : []).map((job: Record<string, unknown>) => {
    const { site, site_type, job_id, ...safe } = job;
    void site; void site_type; void job_id;
    return {
      ...safe,
      title: String(job.title || '').replace(/^\[(?:onlinejobsph|olj)\]\s*/i, ''),
      posted_display: String(job.posted_display || '').replace(/\s*\(OLJ(?: DATE UPDATED)?\)$/i, ''),
    };
  });
  return Response.json({ jobs, count: jobs.length, total: data.total ?? jobs.length, filtered_count: data.filtered_count ?? jobs.length, offset: data.offset ?? 0 }, { headers: { 'Cache-Control': 'no-store' } });
}
