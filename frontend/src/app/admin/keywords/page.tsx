'use client';

import { useEffect, useState } from 'react';

const parseTerms = (text: string) => [...new Set(text.split(/[,\n]/).map(term => term.trim()).filter(Boolean))];

export default function KeywordsPage() {
  const [include, setInclude] = useState('');
  const [exclude, setExclude] = useState('');
  const [notice, setNotice] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    fetch('/api/admin/match-settings').then(response => response.json()).then(data => {
      setInclude((data.include_keywords || []).join('\n'));
      setExclude((data.exclude_keywords || []).join('\n'));
    }).catch(() => setNotice('Unable to load keywords.'));
  }, []);

  async function save() {
    setSaving(true);
    setNotice('');
    try {
      const response = await fetch('/api/admin/match-settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ include_keywords: parseTerms(include), exclude_keywords: parseTerms(exclude) }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Save failed');
      setNotice('Keywords saved. New matching jobs will use these terms.');
    } catch (cause) {
      setNotice(cause instanceof Error ? cause.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return <div className="max-w-4xl">
    <div className="text-xs uppercase tracking-widest text-[#9099a1] mb-2">Matching rules</div>
    <h1 className="text-3xl font-semibold">Alert keywords</h1>
    <p className="text-sm text-[#8a939c] mt-2">New jobs matching any include term can trigger an alert. Exclude terms suppress alerts for that job. All discovered jobs remain in the archive.</p>
    <div className="grid md:grid-cols-2 gap-5 mt-8">
      <div className="card p-5"><label className="font-semibold" htmlFor="include">Include terms</label><p className="text-xs text-[#8a939c] mt-1">One term per line, up to 100.</p><textarea id="include" className="input mt-4 min-h-80" value={include} onChange={event => setInclude(event.target.value)}/></div>
      <div className="card p-5"><label className="font-semibold" htmlFor="exclude">Exclude terms</label><p className="text-xs text-[#8a939c] mt-1">Optional terms, one per line.</p><textarea id="exclude" className="input mt-4 min-h-80" value={exclude} onChange={event => setExclude(event.target.value)}/></div>
    </div>
    <div className="flex items-center gap-4 mt-5"><button className="button" disabled={saving} onClick={() => void save()}>{saving ? 'Saving…' : 'Save keywords'}</button>{notice && <span className="text-sm text-[#65717b]">{notice}</span>}</div>
  </div>;
}
