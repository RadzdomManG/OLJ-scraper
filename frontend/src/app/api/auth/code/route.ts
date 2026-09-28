import { db, codeHash, sessionValue, type CodeRecord } from '@/lib/server';
import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const { code } = await request.json();
    if (typeof code !== 'string' || code.length > 100) return NextResponse.json({ error: 'Enter a valid code' }, { status: 400 });
    const client = db();
    const { data, error } = await client.from('access_codes').select('*').eq('code_hash', codeHash(code)).maybeSingle<CodeRecord>();
    if (error || !data || data.status !== 'active' || (data.expires_at && new Date(data.expires_at) <= new Date()) || (data.max_uses !== null && data.used_count >= data.max_uses)) return NextResponse.json({ error: 'Code is invalid, expired, or fully used' }, { status: 401 });
    const { data: admitted, error: admissionError } = await client.rpc('admit_access_code', { p_id: data.id });
    if (admissionError || !admitted) return NextResponse.json({ error: 'Code is no longer available' }, { status: 401 });
    const response = NextResponse.json({ ok: true });
    response.cookies.set('aurelius_code', sessionValue(data.id), { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', path: '/', maxAge: 60 * 60 * 24 * 30 });
    return response;
  } catch { return NextResponse.json({ error: 'Unable to verify code' }, { status: 500 }); }
}
