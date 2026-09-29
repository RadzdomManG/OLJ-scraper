'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowUpRight, BriefcaseBusiness, RefreshCw, Search, X } from 'lucide-react';

type Job = Record<string, unknown>;
type Source = { id: string; label: string };
const text = (value: unknown) => value == null || String(value).trim() === '' ? 'Not provided' : String(value);
const urlOf = (job: Job) => typeof job.url === 'string' && /^https?:\/\//i.test(job.url) ? job.url : '';
const PHT = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
const exactPht = (value: unknown) => {
  if (typeof value !== 'string' || !value || Number.isNaN(Date.parse(value))) return '';
  return PHT.format(new Date(value)) + ' PHT';
};
const relativeTime = (value: unknown, now: number) => {
  if (typeof value !== 'string' || Number.isNaN(Date.parse(value))) return '';
  const age = now - Date.parse(value);
  if (age < -5 * 60_000) return '';
  if (age < 60_000) return 'Just now';
  const minutes = Math.floor(age / 60_000);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(age / 3_600_000);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(age / 86_400_000);
  return days === 1 ? 'Yesterday' : `${days} days ago`;
};
const timeDisplay = (label: string, exact: string) => <span className="inline-flex flex-col gap-0.5 whitespace-nowrap"><span className="font-medium text-[#34404b]">{label}</span><span className="text-xs text-[#8a949e]">{exact}</span></span>;
const posted = (job: Job, now: number) => {
  const candidate = job.source_posted_at || job.posted_at;
  const value = typeof candidate === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(candidate) ? candidate : null;
  const exact = exactPht(value);
  const relative = relativeTime(value, now);
  if (exact && relative) return timeDisplay(relative, exact);
  if (exact) return timeDisplay('N/A', '');
  const raw = job.source_posted_raw || job.posted_text;
  if (typeof raw === 'string' && raw.trim()) {
    if (/\b(?:ago|just now|today|yesterday)\b/i.test(raw)) return timeDisplay('N/A', '');
    return timeDisplay(raw.trim(), 'Exact time unavailable');
  }
  return timeDisplay('N/A', '');
};
const detected = (job: Job, now: number) => timeDisplay(relativeTime(job.first_seen_at, now) || 'Time unavailable', exactPht(job.first_seen_at) || 'Exact time unavailable');
const salary = (job: Job) => text(job.salary_raw || job.wage_salary);
const work = (job: Job) => text(job.work_type || job.type_of_work);
const score = (job: Job, owner: boolean) => owner ? Number(job.job_score || 0) : Number(job.match_score || 0);
const priority = (job: Job, owner: boolean) => owner ? text(job.priority) : score(job, false) >= 100 ? 'PERFECT MATCH' : score(job, false) >= 80 ? `${score(job, false)}% MATCH` : score(job, false) > 0 ? 'Possible match' : 'General listing';
const priorityClass = (job: Job, owner: boolean) => {
  const value = score(job, owner);
  return value >= 100 ? 'bg-[#dff7e8] text-[#14763c] font-bold'
    : value >= 80 ? 'bg-[#fff2ca] text-[#865a00] font-bold'
    : 'bg-[#f0f3f4] text-[#6d7780]';
};
const recent = (job: Job) => {
  const at = typeof job.first_seen_at === 'string' ? Date.parse(job.first_seen_at) : NaN;
  return Number.isFinite(at) && Date.now() - at < 5 * 60 * 1000 && Date.now() >= at;
};

export default function Jobs({ owner = false, sources = [] }: { owner?: boolean; sources?: Source[] }) {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const fetchedCount = useRef(0);
  const [loadedCount, setLoadedCount] = useState(0);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [source, setSource] = useState('');
  const [workType, setWorkType] = useState('');
  const [salaryMin, setSalaryMin] = useState('');
  const [currency, setCurrency] = useState('');
  const [period, setPeriod] = useState('');
  const [datePreset, setDatePreset] = useState('');
  const [sort, setSort] = useState('detected');
  const [stage, setStage] = useState('');
  const [selected, setSelected] = useState<Job | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [live, setLive] = useState(false);
  const [newUrls, setNewUrls] = useState<Set<string>>(new Set());
  const [clock, setClock] = useState(() => Date.now());

  useEffect(() => { const timer = setTimeout(() => setDebouncedSearch(search), 350); return () => clearTimeout(timer); }, [search]);
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const load = useCallback(async (quiet = false, more = false) => {
    if (more) setLoadingMore(true); else if (!quiet) setLoading(true);
    const params = new URLSearchParams({ offset: String(more ? fetchedCount.current : 0) });
    if (debouncedSearch) params.set('q', debouncedSearch);
    params.set('sort', sort);
    if (owner && source) params.set('source', source);
    if (owner && workType) params.set('work_type', workType);
    if (owner && salaryMin) params.set('salary_min', salaryMin);
    if (owner && currency) params.set('salary_currency', currency);
    if (owner && period) params.set('salary_period', period);
    if (stage && owner) params.set('stage', stage);
    if (owner && datePreset) {
      const now = new Date();
      if (datePreset === 'today') {
        const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
        const part = (type: string) => parts.find(item => item.type === type)?.value || '';
        params.set('since', new Date(`${part('year')}-${part('month')}-${part('day')}T00:00:00+08:00`).toISOString());
      } else {
        const hours = { hour: 1, day: 24, three: 72, week: 168 }[datePreset as 'hour' | 'day' | 'three' | 'week'];
        if (hours) params.set('since', new Date(Date.now() - hours * 3600_000).toISOString());
      }
    }
    try {
      const response = await fetch('/api/jobs?' + params, { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load jobs');
      const incoming: Job[] = Array.isArray(data.jobs) ? data.jobs : [];
      setJobs(current => {
        const existing = more ? [...current, ...incoming] : quiet ? [...incoming, ...current] : incoming;
        const seen = new Set<string>();
        const unique = existing.filter(job => { const id = urlOf(job) || String(job.title) + String(job.first_seen_at); if (seen.has(id)) return false; seen.add(id); return true; });
        return unique;
      });
      fetchedCount.current = more ? fetchedCount.current + incoming.length : quiet ? Math.max(fetchedCount.current, incoming.length) : incoming.length;
      setLoadedCount(fetchedCount.current);
      setTotal(Number(data.filtered_count || 0));
      setUpdated(new Date()); setError('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load jobs'); }
    finally { setLoading(false); setLoadingMore(false); }
  }, [debouncedSearch, source, owner, workType, salaryMin, currency, period, stage, datePreset, sort]);

  useEffect(() => { queueMicrotask(() => { fetchedCount.current = 0; void load(); }); }, [load]);
  useEffect(() => { const interval = setInterval(() => void load(true), 30000); return () => clearInterval(interval); }, [load]);
  useEffect(() => {
    const stream = new EventSource('/api/jobs/stream');
    stream.addEventListener('ready', () => setLive(true));
    stream.addEventListener('job', event => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        if (typeof data.url === 'string') setNewUrls(current => new Set(current).add(data.url));
        void load(true);
      } catch { /* malformed notification: polling still recovers */ }
    });
    stream.addEventListener('expired', () => { stream.close(); router.replace('/login'); router.refresh(); });
    stream.onerror = () => setLive(false);
    return () => { stream.close(); setLive(false); };
  }, [load, router]);

  async function setJobStage(job: Job, nextStage: string) {
    if (!owner || !job.event_key) return;
    const response = await fetch('/api/jobs/stage', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ event_key: job.event_key, stage: nextStage }) });
    if (!response.ok) { setError('Unable to update job'); return; }
    setJobs(current => current.map(item => item.event_key === job.event_key ? { ...item, stage: nextStage } : item));
    setSelected(current => current?.event_key === job.event_key ? { ...current, stage: nextStage } : current);
  }

  return <>
    <div className="flex flex-wrap items-start justify-between gap-4 mb-8"><div><div className="text-xs uppercase tracking-[.18em] text-[#8f98a1] font-semibold mb-2">Opportunities</div><h1 className="text-3xl font-semibold tracking-tight">Jobs <span className="ml-2 align-middle text-xs px-2.5 py-1 rounded-full bg-[#e5f5ea] text-[#29844e]">{live ? 'Live' : 'Updating'}</span></h1><p className="text-[#89919b] text-sm mt-2">{owner ? 'Newly detected jobs appear first.' : 'Every new job appears here. Your niche highlights relevant matches.'} Times are shown in PHT.</p></div>{owner && <button className="button-soft flex items-center gap-2 text-sm" onClick={() => void load()}><RefreshCw size={15}/> Refresh jobs</button>}</div>
    <div className="grid grid-cols-2 gap-3 md:gap-4 mb-6"><div className="card p-4 md:p-5"><div className="text-sm text-[#8d969f]">Stored jobs</div><div className="text-3xl font-semibold mt-2">{total.toLocaleString()}</div></div><div className="card p-4 md:p-5"><div className="text-sm text-[#8d969f]">Last checked</div><div className="text-xl font-semibold mt-3">{updated ? updated.toLocaleTimeString('en-PH', { timeZone: 'Asia/Manila', hour: 'numeric', minute: '2-digit' }) + ' PHT' : 'Not yet'}</div><div className="hidden sm:block text-xs text-[#9da5ac] mt-2">Live updates with automatic refresh fallback</div></div></div>
    <div className="card"><div className={'p-5 grid gap-3 border-b border-[#eff0f2] ' + (owner ? 'sm:grid-cols-2 xl:grid-cols-4' : 'sm:grid-cols-[minmax(0,1fr)_220px]')}>
      <div className={'relative ' + (owner ? 'sm:col-span-2' : '')}><Search size={17} className="absolute left-3 top-3 text-[#9ba3ac]"/><input className="input input-search" aria-label="Search titles or keywords" placeholder="Search titles or keywords..." value={search} onChange={event => setSearch(event.target.value)}/></div>
      {!owner && <select aria-label="Sort jobs" className="input" value={sort} onChange={event => setSort(event.target.value)}><option value="detected">Newest first</option><option value="priority">Priority: best match first</option></select>}
      {owner && <select aria-label="Source" className="input" value={source} onChange={event => setSource(event.target.value)}><option value="">All sources</option>{sources.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select>}
      {owner && <select aria-label="Date" className="input" value={datePreset} onChange={event => setDatePreset(event.target.value)}><option value="">Any detection date</option><option value="hour">Last hour</option><option value="today">Today PHT</option><option value="day">Last 24 hours</option><option value="three">Last 3 days</option><option value="week">Last 7 days</option></select>}
      {owner && <select aria-label="Work type" className="input" value={workType} onChange={event => setWorkType(event.target.value)}><option value="">Any work type</option>{['Full-time','Part-time','Contract','Freelance','Temporary','Hourly','Fixed price','Project'].map(type => <option key={type} value={type}>{type}</option>)}</select>}
      {owner && <input aria-label="Minimum salary" className="input" type="number" min="0" value={salaryMin} onChange={event => setSalaryMin(event.target.value)} placeholder="Minimum salary"/>}
      {owner && <select aria-label="Salary currency" className="input" value={currency} onChange={event => setCurrency(event.target.value)}><option value="">Any currency</option><option value="USD">USD</option><option value="PHP">PHP</option></select>}
      {owner && <select aria-label="Salary period" className="input" value={period} onChange={event => setPeriod(event.target.value)}><option value="">Any pay period</option>{['hour','day','week','month','year','project'].map(item => <option key={item} value={item}>{item}</option>)}</select>}
      {owner && <select aria-label="Job stage" className="input" value={stage} onChange={event => setStage(event.target.value)}><option value="">All stages</option>{['new','saved','applied','ignored'].map(item => <option key={item} value={item}>{item}</option>)}</select>}
      {owner && <select aria-label="Sort jobs" className="input" value={sort} onChange={event => setSort(event.target.value)}><option value="detected">Newest detected</option><option value="priority">Priority: best match first</option><option value="posted">Newest posted</option><option value="salary" disabled={!currency || !period}>Highest salary (choose currency and period)</option></select>}
    </div>
    {error ? <div className="p-12 text-center"><div className="font-semibold">Unable to load jobs</div><p role="alert" className="text-sm text-[#8e97a0] mt-2">{error}</p><button className="button-soft mt-5" onClick={() => void load()}>Try again</button></div>
      : loading ? <div className="p-12 text-center text-[#8e97a0]">Loading opportunities...</div>
      : jobs.length === 0 ? <div className="p-12 text-center"><BriefcaseBusiness className="mx-auto text-[#aab1b8]" size={28}/><div className="font-semibold mt-4">No jobs found</div><p className="text-sm text-[#8e97a0] mt-2">{search ? 'Try another title or keyword.' : 'New jobs will appear here as they are discovered.'}</p></div>
      : <><div className="hidden 2xl:block overflow-x-auto"><table className="w-full min-w-[1240px] text-left text-sm"><thead className="bg-[#fafbfb] text-[#929aa2] text-xs uppercase tracking-wide"><tr>{['Title','Work type','Salary','Job posted','Found','Score','Priority',''].map(label => <th key={label} className="px-4 py-4 font-semibold">{label}</th>)}</tr></thead><tbody>{jobs.map((job,index) => <tr key={urlOf(job) || index} onClick={() => setSelected(job)} className="border-t border-[#f0f1f2] hover:bg-[#fafbfc] cursor-pointer"><td className="px-4 py-4 font-semibold max-w-72"><span className="block truncate">{text(job.title)}</span>{owner && Boolean(job.source) && <span className="text-xs text-[#7d858e]">{String(job.source)}</span>}{(newUrls.has(urlOf(job)) || recent(job)) && <span className="ml-2 text-xs text-[#14763c] font-bold">NEW</span>}</td><td className="px-4 py-4">{work(job)}</td><td className="px-4 py-4">{salary(job)}</td><td className="px-4 py-4 text-[#65707a]">{posted(job,clock)}</td><td className="px-4 py-4 text-[#65707a]">{detected(job,clock)}</td><td className="px-4 py-4">{score(job,owner)}</td><td className="px-4 py-4"><span className={'inline-flex whitespace-nowrap rounded-full px-3 py-1.5 text-xs ' + priorityClass(job,owner)}>{priority(job,owner)}</span></td><td className="px-4 py-4">{urlOf(job) && <a aria-label="Open job" href={urlOf(job)} target="_blank" rel="noopener noreferrer" onClick={event => event.stopPropagation()}><ArrowUpRight size={17}/></a>}</td></tr>)}</tbody></table></div>
      <div className="2xl:hidden divide-y divide-[#eff0f2]">{jobs.map((job,index) => <button key={urlOf(job) || index} onClick={() => setSelected(job)} className="p-5 w-full text-left"><div className="flex justify-between gap-3"><div className="font-semibold">{text(job.title)}</div>{(newUrls.has(urlOf(job)) || recent(job)) && <span className="text-xs text-[#14763c] font-bold">NEW</span>}</div>{owner && Boolean(job.source) && <div className="text-xs text-[#87919a] mt-1">{String(job.source)}</div>}<div className="text-sm text-[#66707b] mt-2">{salary(job)} &middot; {work(job)}</div><div className="text-xs text-[#87919a] mt-2">Job posted: {posted(job,clock)}</div><div className="text-xs text-[#87919a] mt-1">Found: {detected(job,clock)}</div><div className="mt-3"><span className={'inline-flex whitespace-nowrap rounded-full px-3 py-1.5 text-xs ' + priorityClass(job,owner)}>{priority(job,owner)}</span></div></button>)}</div></>}
    <div className="border-t border-[#eff0f2] px-5 py-4 flex items-center justify-between gap-4 text-xs text-[#9199a1]"><span>Showing {jobs.length.toLocaleString()} of {total.toLocaleString()} jobs</span>{loadedCount < total && <button disabled={loadingMore} className="button-soft" onClick={() => void load(false,true)}>{loadingMore ? 'Loading...' : 'Load more jobs'}</button>}</div></div>
    {selected && <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setSelected(null)}><div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-auto p-6 md:p-8" onClick={event => event.stopPropagation()}><div className="flex justify-between gap-4"><div><div className="text-xs uppercase tracking-widest text-[#8d959e]">Job details</div><h2 className="text-2xl font-semibold mt-2">{text(selected.title)}</h2>{owner && Boolean(selected.source) && <div className="text-sm text-[#87919a] mt-2">{String(selected.source)}</div>}</div><button onClick={() => setSelected(null)} aria-label="Close"><X size={20}/></button></div><div className="mt-5"><span className={'inline-flex whitespace-nowrap rounded-full px-3 py-1.5 text-xs ' + priorityClass(selected,owner)}>{priority(selected,owner)}</span></div><div className="grid grid-cols-2 gap-4 my-7 text-sm">{[['Salary',salary(selected)],['Work type',work(selected)],['Company / client',text(selected.company)],['Location',text(selected.location)],['Job posted',posted(selected,clock)],['Found',detected(selected,clock)],['Score',score(selected,owner)],...(owner ? [['Stage',text(selected.stage)],['Notification',selected.notification_sent ? 'Sent' : 'Not sent']] : [])].map(([label,item]) => <div key={String(label)}><div className="text-[#929ba4]">{String(label)}</div><div className="font-semibold mt-1">{item}</div></div>)}</div>{owner && <div className="flex flex-wrap gap-2 mb-6">{['new','saved','applied','ignored'].map(nextStage => <button key={nextStage} className={selected.stage === nextStage ? 'button capitalize' : 'button-soft capitalize'} onClick={() => void setJobStage(selected,nextStage)}>{nextStage}</button>)}</div>}{Array.isArray(selected.skills) && selected.skills.length > 0 && <div className="mb-5 text-sm"><span className="font-semibold">Skills: </span>{selected.skills.join(', ')}</div>}{Array.isArray(selected.niches) && selected.niches.length > 0 && <div className="mb-5 text-sm"><span className="font-semibold">Niches: </span>{selected.niches.join(', ')}</div>}<div className="border-t pt-6"><div className="font-semibold mb-3">Description</div><p className="text-sm text-[#66707b] leading-relaxed whitespace-pre-wrap">{text(selected.description)}</p></div>{urlOf(selected) && <a className="button inline-flex items-center gap-2 mt-7" href={urlOf(selected)} target="_blank" rel="noopener noreferrer">Open job <ArrowUpRight size={16}/></a>}</div></div>}
  </>;
}
