'use client';

import { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight, BriefcaseBusiness, ChevronLeft, ChevronRight, RefreshCw, Search, X } from 'lucide-react';

type Job = Record<string, unknown>;
const PAGE_SIZE = 100;
const value = (item: unknown) => item == null || item === '' ? 'Not specified' : String(item);
const field = (job: Job, ...keys: string[]) => keys.map(key => job[key]).find(item => item != null && item !== '');
const sourceValue = (job: Job, key: 'type_of_work' | 'wage_salary') => {
  const raw = job[key];
  return raw == null || String(raw).trim() === ''
    ? (job.detail_checked_at ? 'Not listed on posting' : 'Checking posting...')
    : String(raw);
};
const jobUrl = (job: Job) => {
  const url = field(job, 'url', 'job_url', 'link');
  return typeof url === 'string' && /^https?:\/\//i.test(url) ? url : undefined;
};

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [filteredCount, setFilteredCount] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [keyword, setKeyword] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [status, setStatus] = useState('');
  const [selected, setSelected] = useState<Job | null>(null);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setDebouncedKeyword(keyword);
    }, 350);
    return () => clearTimeout(timer);
  }, [search, keyword]);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    const params = new URLSearchParams({ offset: String(page * PAGE_SIZE) });
    if (debouncedSearch) params.set('q', debouncedSearch);
    if (debouncedKeyword) params.set('keyword', debouncedKeyword);
    if (status) params.set('status', status);
    try {
      const response = await fetch(`/api/jobs?${params}`, { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load jobs');
      setJobs(Array.isArray(data.jobs) ? data.jobs : []);
      setTotal(Number(data.total || 0));
      setFilteredCount(Number(data.filtered_count || 0));
      setUpdated(new Date());
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load jobs');
    } finally {
      setLoading(false);
    }
  }, [page, debouncedSearch, debouncedKeyword, status]);

  useEffect(() => {
    queueMicrotask(() => void load());
    const timer = setInterval(() => void load(true), 30000);
    return () => clearInterval(timer);
  }, [load]);

  const pages = Math.max(1, Math.ceil(filteredCount / PAGE_SIZE));
  const first = filteredCount ? page * PAGE_SIZE + 1 : 0;
  const last = Math.min((page + 1) * PAGE_SIZE, filteredCount);

  return <>
    <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
      <div>
        <div className="text-xs uppercase tracking-[.18em] text-[#8f98a1] font-semibold mb-2">Opportunities</div>
        <h1 className="text-3xl font-semibold tracking-tight">Jobs <span className="ml-2 align-middle text-xs px-2.5 py-1 rounded-full bg-[#e5f5ea] text-[#29844e]">Live</span></h1>
        <p className="text-[#89919b] text-sm mt-2">Your latest discoveries, updated every 30 seconds.</p>
      </div>
      <button className="button-soft flex items-center gap-2 text-sm" onClick={() => void load()}><RefreshCw size={15}/> Refresh jobs</button>
    </div>

    <div className="grid sm:grid-cols-2 gap-4 mb-6">
      <div className="card p-5"><div className="text-sm text-[#8d969f]">Stored jobs</div><div className="text-3xl font-semibold mt-2">{total.toLocaleString()}</div><div className="text-xs text-[#9da5ac] mt-2">Up to 5,000 newest discoveries</div></div>
      <div className="card p-5"><div className="text-sm text-[#8d969f]">Last refreshed</div><div className="text-xl font-semibold mt-3">{updated ? updated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Not yet'}</div><div className="text-xs text-[#9da5ac] mt-2">Automatic refresh is on</div></div>
    </div>

    <div className="card">
      <div className="p-5 flex flex-col lg:flex-row gap-3 border-b border-[#eff0f2]">
        <div className="relative flex-1"><Search size={17} className="absolute left-3 top-3 text-[#9ba3ac]"/><input className="input pl-10" placeholder="Search all stored jobs..." value={search} onChange={event => { setSearch(event.target.value); setPage(0); }}/></div>
        <input className="input lg:w-48" placeholder="Keyword filter" value={keyword} onChange={event => { setKeyword(event.target.value); setPage(0); }}/>
        <select className="input lg:w-44" value={status} onChange={event => { setStatus(event.target.value); setPage(0); }}><option value="">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
      </div>

      {error ? <div className="p-12 text-center"><div className="text-lg font-semibold">{error === 'Backend offline' ? 'Backend offline' : 'Unable to load jobs'}</div><p className="text-sm text-[#8e97a0] mt-2">{error === 'Backend offline' ? 'Start the watcher or check its public URL.' : error}</p><button className="button-soft mt-5" onClick={() => void load()}>Try again</button></div>
        : loading ? <div className="p-12 text-center text-[#8e97a0]">Loading opportunities...</div>
        : jobs.length === 0 ? <div className="p-12 text-center"><BriefcaseBusiness className="mx-auto text-[#aab1b8]" size={28}/><div className="font-semibold mt-4">No jobs found</div><p className="text-sm text-[#8e97a0] mt-2">Try a different search or wait for the next scan.</p></div>
        : <>
          <div className="hidden md:block overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-[#fafbfb] text-[#929aa2] text-xs uppercase tracking-wide"><tr>{['Title', 'Type of Work', 'Salary', 'Posted', 'Score', 'Priority', ''].map(label => <th key={label} className="px-5 py-4 font-semibold">{label}</th>)}</tr></thead><tbody>
            {jobs.map((job, index) => <tr key={value(field(job, 'event_key', 'id') || index)} onClick={() => setSelected(job)} className="border-t border-[#f0f1f2] hover:bg-[#fafbfc] cursor-pointer"><td className="px-5 py-4 font-semibold max-w-72 truncate">{value(field(job, 'title', 'job_title'))}</td><td className="px-5 py-4 text-[#6f7882]">{sourceValue(job, 'type_of_work')}</td><td className="px-5 py-4">{sourceValue(job, 'wage_salary')}</td><td className="px-5 py-4 text-[#7d858e]">{value(field(job, 'posted_display', 'posted_at', 'posted_date'))}</td><td className="px-5 py-4">{value(field(job, 'job_score', 'score'))}</td><td className="px-5 py-4"><span className="rounded-full bg-[#f0f3f4] px-2.5 py-1 text-xs capitalize">{value(field(job, 'priority', 'status'))}</span></td><td className="px-5 py-4">{jobUrl(job) && <a href={jobUrl(job)} target="_blank" rel="noopener noreferrer" onClick={event => event.stopPropagation()} aria-label="Open job" className="text-[#69737e] hover:text-black"><ArrowUpRight size={17}/></a>}</td></tr>)}
          </tbody></table></div>
          <div className="md:hidden divide-y divide-[#eff0f2]">{jobs.map((job, index) => <button key={value(field(job, 'event_key', 'id') || index)} onClick={() => setSelected(job)} className="p-5 w-full text-left"><div className="font-semibold">{value(field(job, 'title', 'job_title'))}</div><div className="text-sm text-[#84909a] mt-2">{sourceValue(job, 'wage_salary')} | {value(field(job, 'posted_display', 'posted_at'))}</div><div className="text-xs uppercase text-[#82909a] mt-2">{value(field(job, 'priority', 'status'))}</div></button>)}</div>
        </>}

      {!error && !loading && <div className="border-t border-[#eff0f2] px-5 py-4 flex items-center justify-between gap-4 text-xs text-[#9199a1]"><span>Showing {first}-{last} of {filteredCount.toLocaleString()}{filteredCount !== total ? ` matching jobs (${total.toLocaleString()} stored)` : ' jobs'}</span><div className="flex items-center gap-3"><button className="button-soft" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft size={15}/></button><span>Page {page + 1} of {pages}</span><button className="button-soft" disabled={page + 1 >= pages} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight size={15}/></button></div></div>}
    </div>

    {selected && <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setSelected(null)}><div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-auto p-6 md:p-8" onClick={event => event.stopPropagation()}><div className="flex justify-between gap-4"><div><div className="text-xs uppercase tracking-widest text-[#8d959e]">Job details</div><h2 className="text-2xl font-semibold mt-2">{value(field(selected, 'title', 'job_title'))}</h2></div><button onClick={() => setSelected(null)} aria-label="Close"><X size={20}/></button></div><div className="grid grid-cols-2 gap-4 my-7 text-sm">{[['Salary', sourceValue(selected, 'wage_salary')], ['Type of work', sourceValue(selected, 'type_of_work')], ['Hours', field(selected, 'hours_per_week', 'hours')], ['Posted', field(selected, 'posted_display', 'posted_at')], ['Score', field(selected, 'job_score', 'score')], ['Priority', field(selected, 'priority', 'status')]].map(([label, item]) => <div key={String(label)}><div className="text-[#929ba4]">{value(label)}</div><div className="font-semibold mt-1">{value(item)}</div></div>)}</div><div className="border-t pt-6"><div className="font-semibold mb-3">Description</div><p className="text-sm text-[#66707b] leading-relaxed whitespace-pre-wrap">{value(field(selected, 'description', 'job_description', 'body'))}</p></div>{jobUrl(selected) && <a className="button inline-flex items-center gap-2 mt-7" href={jobUrl(selected)} target="_blank" rel="noopener noreferrer">Open job <ArrowUpRight size={16}/></a>}</div></div>}
  </>;
}
