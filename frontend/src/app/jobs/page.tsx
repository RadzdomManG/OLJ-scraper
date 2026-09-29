import { db, owner, viewer } from '@/lib/server';
import { redirect } from 'next/navigation';
import Shell from '@/components/shell';
import Jobs from '@/components/jobs';
const ownerSources = [
  { id: 'onlinejobsph', label: 'OLJ' }, { id: 'freelancer', label: 'Freelancer' },
  { id: 'peopleperhour', label: 'PeoplePerHour' }, { id: 'wellfound', label: 'Wellfound' },
  { id: 'remotive', label: 'Remotive' }, { id: 'contra', label: 'Contra' },
  { id: 'weworkremotely', label: 'We Work Remotely' }, { id: 'guru', label: 'Guru' },
  { id: 'jobicy', label: 'Jobicy' }, { id: 'himalayas', label: 'Himalayas' },
  { id: 'virtualstaff', label: 'VirtualStaff.ph' },
];
export default async function JobsPage() { const isOwner = !!await owner(); if (!isOwner) { const member = await viewer(); if (!member) redirect('/login'); const { data } = await db().from('viewer_preferences').select('code_id').eq('code_id', member.id).maybeSingle(); if (!data) redirect('/preferences'); } return <Shell owner={isOwner}><Jobs owner={isOwner} sources={ownerSources}/></Shell>; }
