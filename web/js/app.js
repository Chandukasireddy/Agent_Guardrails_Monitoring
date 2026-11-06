// App shell: routing between the join screen, the level map, and a level.
// Routes: #/join  #/map  #/play/<level_id>

import { api, getToken, setToken } from "./api.js";
import { isMuted, toggleMute } from "./fx.js";
import { renderJoin } from "./views/join.js";
import { renderMap } from "./views/map.js";
import { renderPlay } from "./views/play.js";

const view = document.getElementById("view");
export const state = { me: null, status: null };

export async function refreshHeader() {
  try {
    state.status = state.status || (await api("/api/status"));
    document.getElementById("provider").textContent = state.status.provider;
    document.getElementById("langfuse-pill").classList.toggle("hidden", !state.status.langfuse);
  } catch { /* server restarting */ }
  if (!getToken()) return;
  try {
    state.me = await api("/api/me");
    const board = await api("/api/scoreboard");
    const mine = board.players.find((p) => p.name === state.me.name && p.team === state.me.team);
    document.getElementById("player-name").textContent = state.me.name;
    document.getElementById("player-team").textContent = `· ${state.me.team}${state.me.role !== "guest" ? " · " + state.me.role : ""}`;
    document.getElementById("points").textContent = mine ? mine.points : 0;
    document.getElementById("player-pill").classList.remove("hidden");
    document.getElementById("points-pill").classList.remove("hidden");
  } catch (e) {
    if (e.status === 401) { setToken(""); location.hash = "#/join"; }
  }
}

async function route() {
  const [, page, arg] = (location.hash || "#/map").split("/");
  if (!getToken() && page !== "join") { location.hash = "#/join"; return; }
  await refreshHeader();
  view.innerHTML = "";
  if (page === "join") return renderJoin(view);
  if (page === "play" && arg) return renderPlay(view, decodeURIComponent(arg));
  return renderMap(view);
}

document.getElementById("logo").onclick = () => (location.hash = "#/map");
const soundBtn = document.getElementById("sound-btn");
soundBtn.textContent = isMuted() ? "🔇" : "🔊";
soundBtn.onclick = () => (soundBtn.textContent = toggleMute() ? "🔇" : "🔊");
window.addEventListener("hashchange", route);
route();
