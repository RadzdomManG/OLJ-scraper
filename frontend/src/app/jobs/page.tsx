import { owner, viewer } from '@/lib/server';
import { redirect } from 'next/navigation';
import Shell from '@/components/shell';
import Jobs from '@/components/jobs';
export default async function JobsPage() { const isOwner = !!await owner(); if (!isOwner && !await viewer()) redirect('/login'); return <Shell owner={isOwner}><Jobs owner={isOwner}/></Shell>; }
