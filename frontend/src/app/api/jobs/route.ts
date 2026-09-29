import { db, owner, viewer } from '@/lib/server';
import { NextRequest } from 'next/server';
import { customerMatch, type Preference, validNicheIds } from '@/lib/customer-match';

const FIELDS = 'event_key,source,source_job_id,source_url,title,company,description,skills,location,category,tags,salary_raw,salary_min,salary_max,salary_currency,salary_period,work_type_raw,work_type,source_posted_raw,source_posted_at,first_seen_at,last_seen_at,detail_checked_at,primary_niche,niches,niche_scores,normalized_tags,quality_flags,stage,notification_sent,owner_score,owner_priority';
const PAGE_SIZE = 100;
const clean = (value: string | null, max = 100) => (value || '').trim().slice(0, max);
const safeSearch = (value: string) => value.replace(/[^\p{L}\p{N} .+#-]/gu, '').trim();
const PLATFORM_NAMES = /\b(?:onlinejobs(?:\.ph)?|olj|freelancer\.com|people\s*per\s*hour(?:\.com)?|wellfound(?:\.com)?|remotive(?:\.com)?|contra(?:\.com)?|we\s*work\s*remotely|guru\.com|jobicy(?:\.com)?|himalayas\.app|virtualstaff(?:\.ph)?)\b/gi;
const customerText = (value: unknown) => typeof value === 'string'
  ? value.replace(PLATFORM_NAMES, '').replace(/\[\s*\]/g, '').replace(/\(\s*\)/g, '').replace(/ {2,}/g, ' ').trim()
  : value;

export async function GET(request: NextRequest) {
  const isOwner = !!await owner();
  const member = isOwner ? null : await viewer();
  if (!isOwner && !member) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  let preferences: Preference = { niches: [], keywords: [] };
  if (member) {
    const { data, error } = await db().from('viewer_preferences').select('niches,keywords').eq('code_id', member.id).maybeSingle();
    if (error) return Response.json({ error: 'Unable to load preferences' }, { status: 500 });
    if (!data) return Response.json({ error: 'Choose your niche first', setup_required: true }, { status: 409 });
    preferences = data as Preference;
  }

  const search = request.nextUrl.searchParams;
  const offset = Number(search.get('offset') || 0);
  const safeOffset = Number.isSafeInteger(offset) && offset >= 0 && offset <= 5000 ? offset : 0;
  const selectedNiche = clean(search.get('niche'));
  const priority = clean(search.get('priority'));
  const allowed = member ? (selectedNiche && preferences.niches.includes(selectedNiche) ? [selectedNiche] : preferences.niches.filter(id => validNicheIds.has(id))) : [];
  if (member && !allowed.length) return Response.json({ jobs: [], count: 0, total: 0, filtered_count: 0, offset: safeOffset });
  const sort = clean(search.get('sort'));
  let query = member
    ? db().rpc(sort === 'score' ? 'customer_jobs_ranked' : 'customer_jobs', { p_niches: allowed, p_min_score: priority === 'perfect' ? 100 : priority === 'strong' ? 80 : 1 }, { count: 'exact' }).select(FIELDS)
    : db().from('jobs').select(FIELDS, { count: 'exact' });
  if (member) {
    // Membership selection and score threshold are applied inside the SQL RPC.
  } else if (selectedNiche && validNicheIds.has(selectedNiche)) query = query.contains('niches', [selectedNiche]);

  const q = safeSearch(clean(search.get('q') || search.get('keyword'), 100));
  if (q) query = query.or('title.ilike.%' + q + '%,description.ilike.%' + q + '%,company.ilike.%' + q + '%');
  const source = clean(search.get('source'));
  if (isOwner && source && /^[a-z0-9_-]+$/.test(source)) query = query.eq('source', source);
  if (isOwner && clean(search.get('stage'))) query = query.eq('stage', clean(search.get('stage')));
  if (isOwner && clean(search.get('notified')) === 'sent') query = query.eq('notification_sent', true);
  if (isOwner && clean(search.get('notified')) === 'not_sent') query = query.eq('notification_sent', false);
  if (isOwner && clean(search.get('status'))) query = query.eq('owner_priority', clean(search.get('status')));
  const workType = clean(search.get('work_type'));
  if (workType) query = query.eq('work_type', workType);
  const salary = Number(search.get('salary_min'));
  if (Number.isFinite(salary) && salary > 0) query = query.gte('salary_min', salary);
  const currency = clean(search.get('salary_currency'));
  const period = clean(search.get('salary_period'));
  if (currency && /^[A-Z]{3}$/.test(currency)) query = query.eq('salary_currency', currency);
  if (period && ['hour', 'day', 'week', 'month', 'year', 'project'].includes(period)) query = query.eq('salary_period', period);
  const from = clean(search.get('date_from'), 10);
  const to = clean(search.get('date_to'), 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(from)) query = query.gte('first_seen_at', from + 'T00:00:00+08:00');
  if (/^\d{4}-\d{2}-\d{2}$/.test(to)) query = query.lt('first_seen_at', new Date(new Date(to + 'T00:00:00+08:00').getTime() + 86400000).toISOString());
  const since = clean(search.get('since'), 40);
  if (since && !Number.isNaN(Date.parse(since))) query = query.gte('first_seen_at', since);
  const after = clean(search.get('after'), 40);
  if (after && !Number.isNaN(Date.parse(after))) query = query.gt('first_seen_at', after);
  if (sort === 'posted') query = query.order('source_posted_at', { ascending: false, nullsFirst: false }).order('first_seen_at', { ascending: false });
  else if (sort === 'salary' && currency && period) query = query.order('salary_max', { ascending: false, nullsFirst: false }).order('first_seen_at', { ascending: false });
  else if (sort !== 'score' || !member) query = query.order('first_seen_at', { ascending: false });
  query = query.range(safeOffset, safeOffset + PAGE_SIZE - 1);
  const { data, error, count } = await query;
  if (error) return Response.json({ error: 'Unable to load jobs' }, { status: 500 });
  const rows: Record<string, unknown>[] = Array.isArray(data) ? data : [];
  const jobs = rows.map((job: Record<string, unknown>) => {
    const title = String(job.title || '').replace(/^\[(?:onlinejobsph|olj)\]\s*/i, '');
    if (isOwner) return { ...job, url: job.source_url, source: job.source, title,
      wage_salary: job.salary_raw, type_of_work: job.work_type, detected_at: job.first_seen_at,
      job_score: job.owner_score, priority: job.owner_priority,
      posted_at: job.source_posted_at || job.source_posted_raw };
    // Customer response excludes owner state and internal event identifiers.
    const safe = {
      title: customerText(title), url: job.source_url, company: customerText(job.company), description: customerText(job.description),
      skills: Array.isArray(job.skills) ? job.skills.map(customerText).filter(Boolean) : [], location: customerText(job.location), category: customerText(job.category),
      salary_raw: job.salary_raw, salary_min: job.salary_min, salary_max: job.salary_max,
      salary_currency: job.salary_currency, salary_period: job.salary_period,
      wage_salary: job.salary_raw, type_of_work: job.work_type,
      work_type_raw: job.work_type_raw, posted_text: customerText(job.source_posted_raw),
      posted_at: job.source_posted_at, first_seen_at: job.first_seen_at,
      primary_niche: job.primary_niche, niches: job.niches,
    };
    return { ...safe, ...customerMatch(job, preferences) };
  });
  return Response.json({ jobs, count: jobs.length, total: count || 0, filtered_count: count || 0, offset: safeOffset }, { headers: { 'Cache-Control': 'no-store' } });
}
