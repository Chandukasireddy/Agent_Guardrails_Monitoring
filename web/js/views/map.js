// The level map and the attack bingo board.

import { api, esc } from "../api.js";
import { toast } from "../fx.js";

const BINGO_KEY = "vaultheist.bingo";
const loadBingo = () => { try { return JSON.parse(localStorage.getItem(BINGO_KEY) || "[]"); } catch { return []; } };
const saveBingo = (v) => { try { localStorage.setItem(BINGO_KEY, JSON.stringify(v)); } catch { /* ignore */ } };

export async function renderMap(view) {
  const [levels, attacks] = await Promise.all([api("/api/levels"), api("/api/attacks")]);
  const solved = levels.filter((l) => l.solved).length;
  view.innerHTML = `
    <div class="map-head">
      <div>
        <h2>The Vaults</h2>
        <div class="muted">${solved} of ${levels.length} cracked. Each level adds a new guardrail.</div>
      </div>
      <a class="btn small" href="#/join" id="switch">Switch player</a>
    </div>
    <div class="levels">
      ${levels.map((l) => `
        <div class="level-card ${l.unlocked ? "" : "locked"} ${l.solved ? "solved" : ""}" data-id="${esc(l.id)}" style="--c:${esc(l.character.color)}">
          <span class="num">#${String(l.order).padStart(2, "0")}</span>
          <div class="avatar">${l.unlocked ? esc(l.character.avatar) : "🔒"}</div>
          <h4>${esc(l.title)}</h4>
          <p>${esc(l.subtitle)}</p>
          <div class="meta"><span class="muted">${esc(l.character.name)}</span><span>⭐ ${l.points}</span></div>
        </div>`).join("")}
    </div>
    <div class="section-title">Attack bingo · tick a technique once you've used it and explained it to a neighbour</div>
    <div class="bingo">
      ${attacks.map((a, i) => `
        <div class="tile" data-i="${i}" title="${esc(a.defense)}">
          <span class="cat">${esc(a.category)}</span>
          <b>${esc(a.name)}</b>
          <span class="muted">${esc(a.description)}</span>
        </div>`).join("")}
    </div>`;

  view.querySelector("#switch").onclick = () => { localStorage.removeItem("vaultheist.token"); };
  view.querySelectorAll(".level-card").forEach((card) => {
    card.onclick = () => {
      if (card.classList.contains("locked")) return toast("Locked. Crack the previous vault first.", "bad");
      location.hash = `#/play/${card.dataset.id}`;
    };
  });
  const done = new Set(loadBingo());
  view.querySelectorAll(".tile").forEach((tile) => {
    const name = attacks[tile.dataset.i].name;
    tile.classList.toggle("done", done.has(name));
    tile.onclick = () => {
      done.has(name) ? done.delete(name) : done.add(name);
      tile.classList.toggle("done", done.has(name));
      saveBingo([...done]);
    };
  });
}
