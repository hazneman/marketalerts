// Cross-device portfolio sync for the Portfolio page.
//
// The portfolio normally lives only in one browser's localStorage. This tiny
// function lets the browser stash a copy in Netlify Blobs (free, no database)
// keyed by a private "sync code" the user generates. Enter the same code on
// another device and it pulls the same portfolio.
//
//   GET  /.netlify/functions/sync?code=XXXX  -> { store, updated_at }
//   PUT  /.netlify/functions/sync?code=XXXX  <- { store, updated_at }
//
// The unguessable code is the only credential (bearer-secret model). The data
// is low-sensitivity — tickers and share counts, no auth/PII — and this is a
// personal tool, so a long random code is a deliberate, documented trade-off.
import { getStore } from '@netlify/blobs'

const CODE_RE = /^[a-z0-9]{8,64}$/i
const MAX_BYTES = 256 * 1024 // a portfolio is small; reject anything unreasonable
const NOSTORE = { 'cache-control': 'no-store' }

function validStore(p) {
  return p && Array.isArray(p.positions) && Array.isArray(p.closed)
}

export default async (req) => {
  const url = new URL(req.url)
  const code = (url.searchParams.get('code') || '').trim()
  if (!CODE_RE.test(code)) {
    return Response.json({ error: 'invalid code' }, { status: 400 })
  }

  const store = getStore({ name: 'portfolios', consistency: 'strong' })

  if (req.method === 'GET') {
    const raw = await store.get(code, { type: 'text' })
    if (!raw) return Response.json({ store: null, updated_at: null }, { headers: NOSTORE })
    try {
      return Response.json(JSON.parse(raw), { headers: NOSTORE })
    } catch {
      return Response.json({ store: null, updated_at: null }, { headers: NOSTORE })
    }
  }

  if (req.method === 'PUT' || req.method === 'POST') {
    const body = await req.text()
    if (body.length > MAX_BYTES) {
      return Response.json({ error: 'too large' }, { status: 413 })
    }
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
    await store.set(code, JSON.stringify(clean))
    return Response.json({ ok: true, updated_at }, { headers: NOSTORE })
  }

  return Response.json({ error: 'method not allowed' }, { status: 405 })
}
