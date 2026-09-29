'use client';
import { useCallback, useEffect, useState } from 'react';
import { Copy, KeyRound, Plus, Trash2 } from 'lucide-react';

type Code = { id: string; label: string; status: string; expires_at: string | null; max_uses: number | null; used_count: number; created_at: string; last_used_at: string | null };
const format = (date: string | null) => date ? new Date(date).toLocaleString() : 'No expiration';
const localDate = (date: string | null) => date ? new Date(new Date(date).getTime() - new Date(date).getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';

export default function CodesPage() {
  const [codes, setCodes] = useState<Code[]>([]);
  const [label, setLabel] = useState('');
  const [expires, setExpires] = useState('');
  const [max, setMax] = useState('');
  const [created, setCreated] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    try {
      const response = await fetch('/api/admin/codes', { cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Unable to load memberships');
      setCodes(data.codes || []); setError('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load memberships'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { queueMicrotask(() => void load()); }, [load]);

  async function create(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const response = await fetch('/api/admin/codes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ label, expires_at: expires, max_uses: max }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not create membership');
      setCreated(data.code); setLabel(''); setExpires(''); setMax(''); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not create membership'); }
    finally { setBusy(false); }
  }
  async function change(id: string, updates: Record<string, unknown>) {
    const response = await fetch('/api/admin/codes', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, ...updates }) });
    if (!response.ok) { const data = await response.json(); setError(data.error || 'Update failed'); return; }
    await load();
  }
  async function remove(id: string) {
    if (!confirm('Delete this membership and its niche settings permanently?')) return;
    const response = await fetch('/api/admin/codes', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
    if (!response.ok) { const data = await response.json(); setError(data.error || 'Delete failed'); return; }
    await load();
  }
  return <>
    <div className="mb-8"><div className="text-xs uppercase tracking-widest text-[#9099a1] mb-2">Access management</div><h1 className="text-3xl font-semibold">Customer memberships</h1><p className="text-sm text-[#8a939c] mt-2">Create one code per customer. Their niche settings belong to that code and remain editable until expiration or revocation.</p></div>
    <div className="grid xl:grid-cols-[340px_1fr] gap-6 items-start">
      <form onSubmit={create} className="card p-6 space-y-4"><div className="flex gap-2 items-center font-semibold"><Plus size={18}/> New membership</div>
        <label className="block text-sm font-semibold">Customer label<input className="input mt-2" value={label} onChange={event => setLabel(event.target.value)} placeholder="Customer name" maxLength={100} required/></label>
        <label className="block text-sm font-semibold">Expires on<input className="input mt-2" type="datetime-local" value={expires} onChange={event => setExpires(event.target.value)}/></label>
        <label className="block text-sm font-semibold">Maximum sign-ins (optional)<input className="input mt-2" type="number" min="1" value={max} onChange={event => setMax(event.target.value)} placeholder="Unlimited"/></label>
        <p className="text-xs text-[#929aa2]">Each successful use of the code counts as a sign-in. Leave blank if the customer may sign in again on other devices.</p>
        <button disabled={busy} className="button w-full">{busy ? 'Generating...' : 'Generate access code'}</button>
        <p className="text-xs text-[#929aa2]">The code is shown once. Copy it now; it cannot be retrieved later.</p>
      </form>
      <div className="space-y-4">
        {created && <div className="card p-5 border-[#abdbba] bg-[#f5fbf6]"><div className="text-sm font-semibold text-[#348153]">New access code — copy it now</div><div className="flex items-center gap-3 mt-3"><code className="font-mono font-semibold break-all">{created}</code><button className="button-soft" aria-label="Copy code" onClick={() => void navigator.clipboard.writeText(created)}><Copy size={16}/></button></div></div>}
        {error && <div role="alert" className="card p-4 text-sm text-red-600">{error}</div>}
        <div className="card overflow-x-auto"><div className="p-5 flex items-center gap-2 font-semibold border-b"><KeyRound size={18}/> Memberships <span className="text-xs text-[#9da5ad] font-normal">({codes.length})</span></div>
          {loading ? <div className="p-10 text-center text-[#929aa2]">Loading memberships...</div> : codes.length === 0 ? <div className="p-10 text-center text-[#929aa2]">No memberships created yet.</div> : <table className="w-full text-left text-sm"><thead className="text-xs uppercase text-[#929aa2] bg-[#fafbfb]"><tr>{['Customer', 'Status', 'Sign-ins', 'Expiration', 'Last sign-in', 'Actions'].map(header => <th className="p-4" key={header}>{header}</th>)}</tr></thead><tbody>{codes.map(code => { const expired = !!code.expires_at && new Date(code.expires_at) <= new Date(); const exhausted = code.max_uses !== null && code.used_count >= code.max_uses; const status = code.status === 'revoked' ? 'Revoked' : expired ? 'Expired' : exhausted ? 'Sign-in limit reached' : 'Active'; return <tr className="border-t border-[#eff0f2]" key={code.id}><td className="p-4 font-semibold">{code.label}</td><td className="p-4"><span className={`rounded-full px-2.5 py-1 text-xs ${status === 'Active' ? 'bg-[#e7f6ec] text-[#28814c]' : 'bg-[#f0f1f2] text-[#7c858e]'}`}>{status}</span></td><td className="p-4">{code.used_count}{code.max_uses !== null ? ` / ${code.max_uses}` : ''}</td><td className="p-4 whitespace-nowrap"><input aria-label={`Expiration for ${code.label}`} className="input min-w-48" type="datetime-local" defaultValue={localDate(code.expires_at)} key={`${code.id}-${code.expires_at}`} onBlur={event => { const value = event.target.value; if (value !== localDate(code.expires_at)) void change(code.id, { expires_at: value }); }}/><div className="text-xs text-[#929aa2] mt-1">{format(code.expires_at)} · edit above</div></td><td className="p-4 whitespace-nowrap">{code.last_used_at ? format(code.last_used_at) : 'Never'}</td><td className="p-4"><div className="flex items-center gap-2">{code.status === 'active' ? <button className="button-soft text-xs" onClick={() => void change(code.id, { status: 'revoked' })}>Revoke</button> : <button className="button-soft text-xs" onClick={() => void change(code.id, { status: 'active' })}>Reactivate</button>}<button className="button-soft" title="Delete" aria-label={`Delete ${code.label}`} onClick={() => void remove(code.id)}><Trash2 size={14}/></button></div></td></tr>; })}</tbody></table>}
        </div>
      </div>
    </div>
  </>;
}
