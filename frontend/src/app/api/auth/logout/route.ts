import { NextResponse } from 'next/server';
export async function POST() { const response = NextResponse.json({ ok: true }); response.cookies.delete('aurelius_code'); response.cookies.delete('aurelius_owner'); return response; }
