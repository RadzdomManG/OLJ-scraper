'use client';

import Link from 'next/link';
import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Activity, BriefcaseBusiness, ChartNoAxesCombined, KeyRound, LogOut, SlidersHorizontal, Sparkles, Tags } from 'lucide-react';

export default function Shell({ owner, children }: { owner: boolean; children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const links = [
    { href: '/jobs', label: 'Jobs', icon: BriefcaseBusiness },
    ...(owner ? [
      { href: '/admin/status', label: 'Backend Status', icon: Activity },
      { href: '/admin/keywords', label: 'Keywords', icon: Tags },
      { href: '/admin/analytics', label: 'Analytics', icon: ChartNoAxesCombined },
      { href: '/admin/codes', label: 'Access Codes', icon: KeyRound },
    ] : [{ href: '/preferences', label: 'My niche', icon: SlidersHorizontal }]),
  ];

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const response = await fetch('/api/auth/session', { cache: 'no-store' });
        if (active && response.status === 401) { router.replace('/login'); router.refresh(); }
      } catch { /* Retry when the connection recovers. */ }
    }
    void check();
    const interval = setInterval(() => void check(), 30000);
    return () => { active = false; clearInterval(interval); };
  }, [router]);

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    router.push('/login');
    router.refresh();
  }

  return <div className="min-h-screen md:flex">
    <aside className="md:w-64 md:min-h-screen shrink-0 bg-white border-r border-[#e9ebed] p-4 md:p-5 flex flex-col">
      <div className="px-1 py-1 md:px-3 md:py-3">
        <div className="flex items-center gap-2 text-xl font-bold tracking-tight text-[#22252b]"><Sparkles size={21} strokeWidth={2.2} aria-hidden="true"/><span>Aurelius</span></div>
        <div className="text-[11px] uppercase tracking-[.18em] text-[#9aa1a9] mt-1">Job Intelligence Portal</div>
      </div>
      <div className="hidden md:block mt-8 text-[11px] uppercase tracking-widest text-[#a2a9b0] px-3 mb-3">Workspace</div>
      <nav className="flex md:flex-col gap-1 overflow-x-auto mt-3 md:mt-0">{links.map(link => {
        const Icon = link.icon;
        return <Link key={link.href} href={link.href} className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm whitespace-nowrap ${path === link.href ? 'bg-[#1e2228] text-white font-semibold' : 'text-[#6d7580] hover:bg-[#f4f5f6]'}`}><Icon size={17}/>{link.label}</Link>;
      })}<button onClick={logout} className="md:hidden flex items-center gap-2 text-sm whitespace-nowrap text-[#727b85] px-3 py-2.5 ml-auto"><LogOut size={17}/> Sign out</button></nav>
      <div className="hidden md:block mt-auto pt-8"><div className="border-t border-[#eceef0] pt-5 px-3"><div className="text-sm font-semibold">{owner ? 'Owner workspace' : 'Member access'}</div><div className="text-xs text-[#9ca3ab] mt-1">Aurelius Portal</div></div><button onClick={logout} className="flex items-center gap-3 text-sm text-[#727b85] px-3 py-3 mt-4 hover:text-black"><LogOut size={17}/> Sign out</button></div>
    </aside>
    <main className="flex-1 min-w-0">
      <header className="h-14 md:h-16 border-b border-[#e9ebed] bg-white flex items-center justify-between gap-3 px-5 md:px-10"><span className="text-sm text-[#8a929a]">Workspace <span className="mx-2">/</span> <span className="text-[#323840] font-semibold">{links.find(link => link.href === path)?.label || 'Jobs'}</span></span><span className="text-xs px-3 py-1.5 rounded-full bg-[#e9f6ed] text-[#27834c] font-semibold whitespace-nowrap">Auto refresh on</span></header>
      <div className="p-5 md:p-10 max-w-[1500px] mx-auto">{children}</div>
    </main>
  </div>;
}
