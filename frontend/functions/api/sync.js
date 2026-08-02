// Cross-device portfolio sync: one JSON value per private sync code, stored
// in Workers KV. Requires a KV namespace bound to the Pages project as
// `PORTFOLIOS` (dashboard: Settings -> Bindings). The unguessable code is the
// only credential (bearer-secret model) — a deliberate, documented trade-off
// for low-sensitivity personal data on a no-account platform.
// GET /api/sync?code=X -> {store, updated_at} · PUT/POST writes
const CODE_RE = /^[a-z0-9]{8,64}$/i
const MAX_BYTES = 256 * 1024
const NOSTORE = { 'cache-control': 'no-store' }

function validCode(url) {
  const code = (url.searchParams.get('code') || '').trim()
  return CODE_RE.test(code) ? code : null
}

function validStore(p) {
  return p && Array.isArray(p.positions) && Array.isArray(p.closed)
}

export async function onRequestGet({ request, env }) {
  const code = validCode(new URL(request.url))
  if (!code) return Response.json({ error: 'invalid code' }, { status: 400 })
  if (!env.PORTFOLIOS) return Response.json({ error: 'storage not configured' }, { status: 500 })

  const raw = await env.PORTFOLIOS.get(code)
  if (!raw) return Response.json({ store: null, updated_at: null }, { headers: NOSTORE })
  try {
    return Response.json(JSON.parse(raw), { headers: NOSTORE })
  } catch {
    return Response.json({ store: null, updated_at: null }, { headers: NOSTORE })
  }
}

async function write({ request, env }) {
  const code = validCode(new URL(request.url))
  if (!code) return Response.json({ error: 'invalid code' }, { status: 400 })
  if (!env.PORTFOLIOS) return Response.json({ error: 'storage not configured' }, { status: 500 })

  const body = await request.text()
  if (body.length > MAX_BYTES) return Response.json({ error: 'too large' }, { status: 413 })
  let parsed
  try {
    parsed = JSON.parse(body)
  } catch {
    return Response.json({ error: 'invalid json' }, { status: 400 })
  }
  if (!validStore(parsed?.store)) {
    return Response.json({ error: 'invalid portfolio' }, { status: 400 })
  }
  const updated_at =
    typeof parsed.updated_at === 'string' ? parsed.updated_at : new Date().toISOString()
  const clean = {
    store: { positions: parsed.store.positions, closed: parsed.store.closed },
    updated_at,
  }
  await env.PORTFOLIOS.put(code, JSON.stringify(clean))
  return Response.json({ ok: true, updated_at }, { headers: NOSTORE })
}

export const onRequestPut = write
export const onRequestPost = write // sendBeacon flushes arrive as POST
