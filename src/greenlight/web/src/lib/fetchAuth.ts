import { getAuthToken } from './firebase';

// Prod: REST goes direct to Cloud Run — Firebase Hosting rewrites have a hard
// 60s response cap, which 502s long calls (table-read, coverage). WS already
// goes direct via VITE_WS_BASE for the same reason.
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

const origFetch = window.fetch.bind(window);
let installed = false;

/** Patch window.fetch to attach Authorization: Bearer <idToken> to /api calls. */
export function installFetchAuth(): void {
  if (installed) return;
  installed = true;

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url =
      typeof input === 'string'
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    if (!url.startsWith('/api')) return origFetch(input, init);

    const token = await getAuthToken();
    if (!token) return origFetch(input, init);

    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    return origFetch(API_BASE + url, { ...init, headers });
  };
}
