import { owner, viewer } from '@/lib/server';
import { redirect } from 'next/navigation';
import Shell from '@/components/shell';
import Preferences from '@/components/preferences';

export default async function PreferencesPage() {
  if (await owner()) redirect('/jobs');
  if (!await viewer()) redirect('/login');
  return <Shell owner={false}><Preferences/></Shell>;
}
