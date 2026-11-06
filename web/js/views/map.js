// The vault list: a progress track, a clear next step, and one row per challenge.

import { api, esc } from "../api.js";
import { icon, hasIcon } from "../icons.js";
import { toast } from "../fx.js";

export async function renderMap(view) {
  const levels = await api("/api/levels");
  const solved = levels.filter((l) => l.solved).length;
  const next = levels.find((l) => l.unlocked && !l.solved);
  const pct = levels.length ? Math.round((solved / levels.length) * 100) : 0;
  const stateOf = (l) => (l.solved ? "cracked" : l.unlocked ? "open" : "locked");
  const label = { cracked: "Cracked", open: "Open", locked: "Locked" };

  view.innerHTML = `
    <div class="page">
      <header class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Five challenges, one guard each</p>
          <h1>${solved === levels.length ? "Every vault is open." : "Break in, one vault at a time."}</h1>
          <p class="muted">${solved} of ${levels.length} cracked. Each vault teaches one way attackers reach an AI system, and one defense that stops them.</p>
        </div>
        ${next
          ? `<a class="btn primary big" href="#/play/${encodeURIComponent(next.id)}">${icon("play", 16)} Continue: ${esc(next.title)}</a>`
          : `<span class="badge cracked big">${icon("badge-check", 16)} All cracked</span>`}
      </header>

      <ol class="track" aria-label="Progress, ${pct} percent">
        ${levels.map((l) => {
          const st = stateOf(l);
          return `<li class="track-step ${st}">
            <span class="track-dot" aria-hidden="true">${st === "cracked" ? icon("check", 14) : st === "locked" ? icon("lock", 12) : icon(hasIcon(l.character.avatar) ? l.character.avatar : "shield-check", 14)}</span>
            <span class="track-label">${esc(l.title)}</span>
          </li>`;
        }).join("")}
      </ol>

      <div class="vault-grid">
        ${levels.map((l) => {
          const st = stateOf(l);
          const locked = st === "locked";
          const prev = levels.find((x) => x.order === l.order - 1);
          return `
          <article class="vault ${st}" data-id="${esc(l.id)}">
            <header class="vault-top">
              <span class="vault-icon" aria-hidden="true">${icon(hasIcon(l.character.avatar) ? l.character.avatar : "shield-check", 22)}</span>
              <span class="badge ${st}">${label[st]}</span>
            </header>
            <p class="vault-no">Vault ${String(l.order).padStart(2, "0")} · ${l.points} pts</p>
            <h2>${esc(l.title)}</h2>
            <p class="muted">${esc(l.subtitle)}</p>
            <footer class="vault-foot">
              <span class="guard-name">${icon("shield-check", 13)} ${esc(l.character.name)}</span>
              ${locked
                ? `<button class="btn small ghost" type="button" data-locked="${esc(prev ? prev.title : "")}" aria-disabled="true">${icon("lock", 13)} Locked</button>`
                : `<a class="btn small ${l.id === next?.id ? "primary" : ""}" href="#/play/${encodeURIComponent(l.id)}">${st === "cracked" ? "Revisit" : "Enter"} ${icon("arrow-right", 13)}</a>`}
            </footer>
          </article>`;
        }).join("")}
      </div>

      <p class="small-print switch-line">Playing on a shared laptop? ${icon("users", 13)}
        <a href="#/join" id="switch">Switch user</a></p>
    </div>`;

  view.querySelector("#switch").onclick = (e) => { e.preventDefault(); location.hash = "#/join"; };
  view.querySelectorAll("button[data-locked]").forEach((btn) => {
    btn.onclick = () => toast(`Locked. Crack "${btn.dataset.locked}" first.`, "bad");
  });
}
