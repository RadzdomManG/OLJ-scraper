'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

type Niche = { id: string; label: string; group: string };
export default function Preferences() {
  const router = useRouter();
  const [niches, setNiches] = useState<Niche[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { void (async () => {
    try {
      const response = await fetch('/api/preferences', { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load your settings');
      setNiches(data.niches || []);
      setSelected(data.selected?.niches || []);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load your settings'); }
    finally { setLoading(false); }
  })(); }, []);
  function toggle(id: string) { setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id]); }
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const response = await fetch('/api/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ niches: selected }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to save your settings');
      router.push('/jobs'); router.refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to save your settings'); }
    finally { setBusy(false); }
  }
  return <div className="max-w-4xl"><div className="mb-8"><div className="text-xs uppercase tracking-widest text-[#9099a1] mb-2">Your workspace</div><h1 className="text-3xl font-semibold">Choose your niche</h1><p className="text-sm text-[#7c858e] mt-2">Every job stays visible. Your choices highlight jobs that match your interests. You can change them anytime while your membership is active.</p></div>
    {loading ? <div className="card p-8">Loading your niches...</div> : <form onSubmit={save} className="card p-6 space-y-7"><div className="space-y-7">{[...new Set(niches.map(niche => niche.group))].map(group => <div key={group}><h2 className="font-semibold mb-3">{group}</h2><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{niches.filter(niche => niche.group === group).map(niche => <label key={niche.id} className={`flex gap-3 items-center rounded-xl border px-4 py-3 cursor-pointer ${selected.includes(niche.id) ? 'border-[#8dd2a5] bg-[#eff9f2]' : 'border-[#e6e9eb]'}`}><input type="checkbox" checked={selected.includes(niche.id)} onChange={() => toggle(niche.id)}/><span className="text-sm font-medium">{niche.label}</span></label>)}</div></div>)}</div><p className="text-sm text-[#75818a]">Match scores measure role and skill signals in the posting. They do not guarantee personal fit.</p>{error && <p role="alert" className="text-red-600 text-sm">{error}</p>}<button className="button" disabled={busy}>{busy ? 'Saving...' : 'Save and view jobs'}</button></form>}</div>;
}
