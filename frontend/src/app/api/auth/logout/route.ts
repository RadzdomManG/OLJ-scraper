import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { db, ownerTokenHash } from '@/lib/server';
export async function POST() {
  const token = (await cookies()).get('aurelius_owner')?.value;
  if (token) await db().from('owner_sessions').update({ revoked_at: new Date().toISOString() }).eq('token_hash', ownerTokenHash(token));
  const response = NextResponse.json({ ok: true });
  response.cookies.delete('aurelius_code'); response.cookies.delete('aurelius_owner');
  return response;
}
