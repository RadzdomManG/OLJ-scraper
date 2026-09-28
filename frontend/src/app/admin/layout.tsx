import { owner } from '@/lib/server';
import { redirect } from 'next/navigation';
import Shell from '@/components/shell';
export default async function AdminLayout({ children }: { children: React.ReactNode }) { if (!await owner()) redirect('/login'); return <Shell owner>{children}</Shell>; }
