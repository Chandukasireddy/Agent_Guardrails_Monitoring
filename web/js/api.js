// Tiny API client. The player token lives in localStorage so a refresh keeps you in the game.

const KEY = "vaultheist.token";

export function getToken() {
  try { return localStorage.getItem(KEY) || ""; } catch { return ""; }
}
export function setToken(token) {
  try { token ? localStorage.setItem(KEY, token) : localStorage.removeItem(KEY); } catch { /* private mode */ }
}

export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-Player-Token": getToken(), ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const err = new Error((data && data.detail) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
