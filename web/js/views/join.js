// Welcome screen: pick one of the three demo users. They share this laptop, and each keeps its own progress.

import { api, setToken, esc } from "../api.js";
import { icon } from "../icons.js";
import { toast } from "../fx.js";

export const DEMO_USERS = ["admin", "intern", "customer"];

export function renderJoin(view) {
  view.innerHTML = `
    <section class="welcome" aria-labelledby="join-title">
      <div class="welcome-copy">
        <span class="welcome-mark" aria-hidden="true">${icon("shield-check", 30)}</span>
        <p class="eyebrow">Workshop game · AI security</p>
        <h1 id="join-title">Welcome to Token Vault</h1>
        <p class="lede">Five AI guards each protect a fake secret. Talk to them, find the way past their defenses, and paste the secret into the vault.</p>
        <ol class="steps">
          <li>${icon("message-square", 16)}<span>Chat with the guard and watch each check light up.</span></li>
          <li>${icon("route", 16)}<span>Work out which check stopped you, and why.</span></li>
          <li>${icon("lock-keyhole", 16)}<span>Paste the secret into the vault box to crack it.</span></li>
        </ol>
      </div>
      <div class="welcome-users">
        <p class="eyebrow">Who is playing?</p>
        <ul class="user-list">
          ${DEMO_USERS.map((u) => `
            <li>
              <button class="user-card" type="button" data-user="${u}">
                <span class="user-avatar large" aria-hidden="true">${u[0].toUpperCase()}</span>
                <span class="user-copy"><b>${u[0].toUpperCase() + u.slice(1)}</b><span class="muted">Continue with this user's progress</span></span>
                <span class="chev" aria-hidden="true">${icon("chevron-right", 18)}</span>
              </button>
            </li>`).join("")}
        </ul>
        <p class="small-print">Three demo accounts on one laptop. Switch any time from the top bar. Every secret here is fake.</p>
      </div>
    </section>`;
  view.querySelectorAll(".user-card").forEach((btn) => {
    btn.onclick = async () => {
      try {
        const r = await api(`/api/demo/${esc(btn.dataset.user)}`, { method: "POST" });
        setToken(r.token);
        location.hash = "#/map";
      } catch (err) {
        toast(err.message, "bad");
      }
    };
  });
}
