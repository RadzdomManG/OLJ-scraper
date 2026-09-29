import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { createOwnerSession, db, owner, ownerTokenHash, sessionValue, SESSION_MAX_AGE, viewer } from '@/lib/server';

export async function GET() {
  const existing = (await cookies()).get('aurelius_owner')?.value;
  const user = await owner();
  if (user) {
    const response = NextResponse.json({ role: 'owner' });
    const { data } = existing ? await db().from('owner_sessions').select('token_hash').eq('token_hash', ownerTokenHash(existing)).maybeSingle() : { data: null };
    const token = data ? existing! : await createOwnerSession(user.id);
    response.cookies.set('aurelius_owner', token, { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', path: '/', maxAge: SESSION_MAX_AGE });
    return response;
  }
  const member = await viewer();
  if (member) {
    const response = NextResponse.json({ role: 'customer', expires_at: member.expires_at });
    response.cookies.set('aurelius_code', sessionValue(member.id), { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', path: '/', maxAge: SESSION_MAX_AGE });
    return response;
  }
  const response = NextResponse.json({ error: 'Session expired' }, { status: 401 });
  response.cookies.delete('aurelius_code'); response.cookies.delete('aurelius_owner');
  return response;
}
