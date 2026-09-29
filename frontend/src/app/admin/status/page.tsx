'use client';

import { useCallback, useEffect, useState } from 'react';
import { Activity, RefreshCw, ScanSearch } from 'lucide-react';

type Source = {
  name: string;
  type: string;
  url?: string;
  enabled?: boolean;
  status?: string;
  reason?: string;
  poll_interval_seconds?: number;
  last_checked_at?: string;
  last_error?: string;
  last_fetched?: number;
};
type Status = Record<string, unknown> & { sources?: Source[] };

export default function StatusPage() {
  const [data, setData] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [notice, setNotice] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/admin/backend');
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to load status');
      setData(result);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Backend offline');
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { queueMicrotask(() => void load()); }, [load]);

  async function scan() {
    setScanning(true);
    setNotice('');
    try {
      const response = await fetch('/api/admin/backend', { method: 'POST' });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Scan failed');
      setNotice(result.message || 'Scan requested');
      await load();
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Scan failed');
    } finally {
      setScanning(false);
    }
  }

  async function updateSource(source: Source, enabled: boolean, interval_seconds = source.poll_interval_seconds || 300) {
    try {
      const response = await fetch(`/api/admin/sources/${source.type}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled, interval_seconds }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Unable to update source');
      await load();
      setNotice(`${source.name} settings saved.`);
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Unable to update source');
    }
  }

  const items = [
    ['Watcher running', data?.watcher_running ? 'Running' : 'Stopped'],
    ['Last check', data?.last_check_local || data?.last_check_at || '—'],
    ['Events', data?.events_count ?? '—'],
    ['Seen jobs', data?.seen_count ?? '—'],
    ['Scan status', data?.scan_status || '—'],
    ['Last error', data?.last_error || 'None'],
  ];

  return <>
    <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
      <div><div className="text-xs uppercase tracking-widest text-[#9099a1] mb-2">System health</div><h1 className="text-3xl font-semibold">Backend Status</h1><p className="text-sm text-[#8a939c] mt-2">Monitor the watcher and its job sources.</p></div>
      <div className="flex gap-2"><button className="button-soft flex gap-2 items-center" onClick={load}><RefreshCw size={16}/> Refresh</button><button className="button flex gap-2 items-center" disabled={scanning} onClick={scan}><ScanSearch size={16}/>{scanning ? 'Scanning…' : 'Scan now'}</button></div>
    </div>
    {notice && <div className="card p-4 mb-5 text-sm">{notice}</div>}
    {error ? <div className="card p-10 text-center"><Activity className="mx-auto text-[#a9b1b9]"/><h2 className="font-semibold mt-4">Backend offline</h2><p className="text-sm text-[#8c959d] mt-2">{error}</p></div>
      : loading ? <div className="card p-10 text-center text-[#8c959d]">Loading status…</div>
      : <>
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">{items.map(([label, value]) => <div className="card p-6" key={String(label)}><div className="text-sm text-[#8d969f]">{String(label)}</div><div className="text-xl font-semibold mt-3 break-words">{String(value)}</div></div>)}</div>
        <h2 className="text-xl font-semibold mt-8 mb-4">Job sources</h2>
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">{data?.sources?.map(source => <div className="card p-5" key={source.type}>
          <div className="flex justify-between gap-2"><div className="font-semibold">{source.name}</div><div className={source.status === 'blocked' || source.status === 'error' ? 'text-xs font-semibold text-amber-700' : 'text-xs font-semibold text-green-700'}>{!source.enabled ? 'Disabled' : source.status === 'blocked' ? 'Blocked' : source.status === 'error' ? 'Error' : source.last_checked_at ? 'Connected' : 'Waiting for first check'}</div></div>
          <div className="text-sm text-[#87919a] mt-3">{source.last_error || String(source.last_fetched ?? 0) + ' relevant jobs at last check'}</div>
          <div className="flex items-center gap-3 mt-4"><label className="text-sm flex items-center gap-2"><input type="checkbox" checked={!!source.enabled} onChange={event => void updateSource(source, event.target.checked)}/> Enabled</label><label className="text-xs text-[#7c8791]">Interval <input aria-label={`${source.name} interval in seconds`} className="input ml-1 !w-24 !py-1" type="number" min={source.type === 'remotive' ? 21600 : source.type === 'onlinejobsph' ? 20 : source.type === 'peopleperhour' || source.type === 'contra' ? 1800 : source.type === 'wellfound' ? 120 : 60} defaultValue={source.poll_interval_seconds || 300} key={`${source.type}-${source.poll_interval_seconds}`} onBlur={event => { const seconds = Number(event.target.value); if (seconds !== source.poll_interval_seconds) void updateSource(source, !!source.enabled, seconds); }}/></label><span className="text-xs text-[#9ca4ac]">seconds</span></div>
          {source.last_checked_at && <div className="text-xs text-[#9ca4ac] mt-1">Last checked {new Date(source.last_checked_at).toLocaleString()}</div>}
          {source.type === 'remotive' && <div className="text-xs text-[#9ca4ac] mt-2">The public feed delays listings by 24 hours.</div>}
          {source.url && <a className="inline-block text-xs font-semibold text-[#3a679b] mt-3 hover:underline" href={source.url} target="_blank" rel="noopener noreferrer">Open source ↗</a>}
        </div>)}</div>
      </>}
  </>;
}
