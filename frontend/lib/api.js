// Tiny fetch wrapper. Uses relative URLs so Next.js rewrites proxy to FastAPI.
const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => req("/health"),
  process: (text, language) =>
    req("/api/process", { method: "POST", body: JSON.stringify({ text, language }) }),
  schemes: () => req("/api/schemes"),
  saveApplication: (payload) =>
    req("/api/applications", { method: "POST", body: JSON.stringify(payload) }),
};
