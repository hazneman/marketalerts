// Host-aware serverless endpoints. The same frontend runs on both hosting
// stacks during the Netlify -> Cloudflare Pages migration:
//   Netlify          /.netlify/functions/<name>   (frontend/netlify/functions)
//   Cloudflare Pages /api/<name>                  (frontend/functions/api)
// Local dev/preview gets the Cloudflare-style path; both stacks' callers
// already degrade gracefully when the endpoint isn't reachable.
export function fnUrl(name: string): string {
  const onNetlify =
    typeof location !== 'undefined' && location.hostname.endsWith('.netlify.app')
  return onNetlify ? `/.netlify/functions/${name}` : `/api/${name}`
}
