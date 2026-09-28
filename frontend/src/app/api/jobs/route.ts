import { backend, owner, viewer } from '@/lib/server';
export async function GET() {
  if (!await owner() && !await viewer()) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const response = await backend('/api/jobs?limit=500');
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
  return Response.json({ jobs, count: jobs.length }, { headers: { 'Cache-Control': 'no-store' } });
}
