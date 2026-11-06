// App shell: sign-in as one of the demo users (admin, intern, customer), the vault list, and a single vault.
// Routes: #/join  #/map  #/play/<level_id>

import { api, getToken, setToken, esc } from "./api.js";
import { icon } from "./icons.js";
import { renderJoin, DEMO_USERS } from "./views/join.js";
import { renderMap } from "./views/map.js";
import { renderPlay } from "./views/play.js";

const view = document.getElementById("view");
export const state = { me: null, status: null };

document.getElementById("brand-icon").innerHTML = icon("shield-check", 20);

function setCrumbs(parts) {
  document.getElementById("crumbs").innerHTML = parts
    .map((p) => (p.href ? `<a href="${esc(p.href)}">${esc(p.label)}</a>` : `<span>${esc(p.label)}</span>`))
    .join(`<span class="sep" aria-hidden="true">/</span>`);
}

// Demo users share one laptop: switching is a single select, and each user keeps its own progress.
function paintUserSwitch(current) {
  const wrap = document.getElementById("user-switch");
  const select = document.getElementById("user-select");
  wrap.classList.remove("hidden");
  document.getElementById("user-initial").textContent = current[0].toUpperCase();
  select.innerHTML = DEMO_USERS.map((u) => `<option value="${u}" ${u === current ? "selected" : ""}>${u[0].toUpperCase() + u.slice(1)}</option>`).join("");
  select.onchange = async () => {
    const r = await api(`/api/demo/${select.value}`, { method: "POST" });
    setToken(r.token);
    location.hash = "#/map";
    route();
  };
}

export async function refreshHeader() {
  try {
    state.status = state.status || (await api("/api/status"));
    document.getElementById("provider").textContent = state.status.provider;
    document.getElementById("langfuse-pill").classList.toggle("hidden", !state.status.langfuse);
  } catch { /* server restarting */ }
  if (!getToken()) {
    document.getElementById("user-switch").classList.add("hidden");
    return;
  }
  try {
    state.me = await api("/api/me");
    paintUserSwitch(state.me.name.toLowerCase());
  } catch (e) {
    if (e.status === 401) { setToken(""); location.hash = "#/join"; }
  }
}

async function route() {
  const [, page, arg] = (location.hash || "#/map").split("/");
  if (!getToken() && page !== "join") { location.hash = "#/join"; return; }
  await refreshHeader();
  view.innerHTML = "";
  view.focus({ preventScroll: true });
  if (page === "join") {
    setCrumbs([{ label: "Sign in" }]);
    return renderJoin(view);
  }
  if (page === "play" && arg) {
    setCrumbs([{ label: "Vaults", href: "#/map" }, { label: "Vault" }]);
    return renderPlay(view, decodeURIComponent(arg), setCrumbs);
  }
  setCrumbs([{ label: "Vaults" }]);
  return renderMap(view);
}

window.addEventListener("hashchange", route);
route();
