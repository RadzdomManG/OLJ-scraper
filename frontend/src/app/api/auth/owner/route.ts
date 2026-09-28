import { db } from '@/lib/server';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { email, password } = await request.json();
    if (typeof email !== 'string' || typeof password !== 'string' || email.toLowerCase() !== process.env.OWNER_EMAIL?.toLowerCase()) return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
    const { data, error } = await db().auth.signInWithPassword({ email, password });
    if (error || !data.session || data.user.email?.toLowerCase() !== process.env.OWNER_EMAIL?.toLowerCase()) return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 });
    const response = NextResponse.json({ ok: true });
    response.cookies.set('aurelius_owner', data.session.access_token, { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', path: '/', maxAge: data.session.expires_in });
    return response;
  } catch { return NextResponse.json({ error: 'Owner login unavailable' }, { status: 500 }); }
}
