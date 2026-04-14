function resolveApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (configured) {
    return configured.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;

    // On RunPod, frontend is typically <podid>-3000.proxy.runpod.net.
    // Derive backend as the matching <podid>-8000.proxy.runpod.net.
    const runpodHost = hostname.match(/^(.*)-3000\.proxy\.runpod\.net$/);
    if (runpodHost) {
      return `${protocol}//${runpodHost[1]}-8000.proxy.runpod.net/api`;
    }
  }

  return "http://localhost:8000/api";
}

export const API_BASE = resolveApiBase();

export async function api(path: string, init?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}
