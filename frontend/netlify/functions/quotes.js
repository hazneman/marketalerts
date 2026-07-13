// Live-quote proxy for the Portfolio page's "Update prices" button.
// Browsers can't call Yahoo directly (no CORS), so this tiny stateless
// function fetches quotes server-side for the requested symbols only.
// GET /.netlify/functions/quotes?symbols=AAPL,SAP.DE,THYAO.IS
export default async (req) => {
  const url = new URL(req.url)
  const raw = url.searchParams.get('symbols') || ''
  const symbols = [...new Set(
    raw.split(',').map((s) => s.trim().toUpperCase())
      .filter((s) => /^[A-Z0-9.^=-]{1,12}$/.test(s)),
  )].slice(0, 30) // portfolio-sized requests only

  if (symbols.length === 0) {
    return Response.json({ error: 'no valid symbols' }, { status: 400 })
  }

  const prices = {}
  await Promise.all(symbols.map(async (sym) => {
    try {
      const r = await fetch(
        `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?range=1d&interval=5m`,
        { headers: { 'User-Agent': 'Mozilla/5.0' } },
      )
      if (!r.ok) return
      const j = await r.json()
      const meta = j?.chart?.result?.[0]?.meta
      if (meta && typeof meta.regularMarketPrice === 'number') {
        prices[sym] = {
          price: meta.regularMarketPrice,
          time: meta.regularMarketTime ?? null,
          currency: meta.currency ?? null,
        }
      }
    } catch {
      // symbol simply omitted from the response; frontend falls back to scan price
    }
  }))

  return Response.json(
    { prices, fetched_at: new Date().toISOString() },
    { headers: { 'cache-control': 'no-store' } },
  )
}
