import { db, owner, viewer } from '@/lib/server';
import { randomUUID } from 'node:crypto';

export const runtime = 'nodejs';
export const maxDuration = 60;

export async function GET(request: Request) {
  const isOwner = !!await owner();
  const member = isOwner ? null : await viewer();
  if (!isOwner && !member) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  const client = db();
  const preferences = member ? await client.from('viewer_preferences').select('niches').eq('code_id', member.id).maybeSingle() : null;
  if (member && (preferences?.error || !preferences?.data)) return Response.json({ error: 'Choose your niche first' }, { status: 409 });
  const selected: string[] = preferences?.data?.niches || [];
  const encoder = new TextEncoder();
  let channel: ReturnType<typeof client.channel> | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let closed = false;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const send = (event: string, payload: unknown) => {
        if (!closed) controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`));
      };
      const close = async () => {
        if (closed) return;
        closed = true;
        if (heartbeat) clearInterval(heartbeat);
        if (timeout) clearTimeout(timeout);
        if (channel) await client.removeChannel(channel);
        try { controller.close(); } catch { /* already closed */ }
      };
      channel = client.channel(`jobs-${randomUUID()}`).on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'jobs' }, async payload => {
        const job = payload.new as Record<string, unknown>;
        if (member) {
          const { data } = await client.from('access_codes').select('status,expires_at').eq('id', member.id).maybeSingle();
          if (!data || data.status !== 'active' || (data.expires_at && new Date(data.expires_at) <= new Date())) { send('expired', {}); void close(); return; }
          if (!Array.isArray(job.niches) || !job.niches.some(niche => selected.includes(String(niche)))) return;
        }
        send('job', { url: job.source_url, first_seen_at: job.first_seen_at });
      }).subscribe(status => { if (status === 'SUBSCRIBED') send('ready', { ok: true }); else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') send('status', { realtime: false }); });
      heartbeat = setInterval(async () => {
        if (member) {
          const { data } = await client.from('access_codes').select('status,expires_at').eq('id', member.id).maybeSingle();
          if (!data || data.status !== 'active' || (data.expires_at && new Date(data.expires_at) <= new Date())) { send('expired', {}); void close(); return; }
        }
        send('ping', { at: new Date().toISOString() });
      }, 15000);
      timeout = setTimeout(() => void close(), 55000);
      request.signal.addEventListener('abort', () => void close(), { once: true });
    },
    cancel() {
      closed = true;
      if (heartbeat) clearInterval(heartbeat);
      if (timeout) clearTimeout(timeout);
      if (channel) void client.removeChannel(channel);
    },
  });
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive', 'X-Accel-Buffering': 'no' } });
}
