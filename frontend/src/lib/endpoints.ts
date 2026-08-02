// Serverless endpoints. Hosting is Cloudflare Pages: functions live in
// frontend/functions/api/* and are served under /api/<name>. Kept as a helper
// so a future host change is one edit; local dev/preview hits the same paths
// (callers degrade gracefully when no runtime is attached).
export function fnUrl(name: string): string {
  return `/api/${name}`
}
