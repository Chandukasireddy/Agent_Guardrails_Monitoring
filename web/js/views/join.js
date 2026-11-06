import { api, setToken } from "../api.js";
import { sfx, toast } from "../fx.js";

export function renderJoin(view) {
  view.innerHTML = `
    <section class="join">
      <div class="panel join-card">
        <div class="vault-door">🔐</div>
        <h1>VAULT HEIST</h1>
        <p class="muted">Every guard protects a fake secret. Break their guardrails, crack the vault,
        and learn how real AI systems should be defended.</p>
        <form id="join-form">
          <input class="field" id="name" placeholder="Your codename" maxlength="40" autocomplete="off" required />
          <input class="field" id="team" placeholder="Team name (optional)" maxlength="40" autocomplete="off" />
          <button class="btn primary" type="submit">Enter the heist →</button>
        </form>
        <p class="muted" style="font-size:12px;margin-top:16px">All secrets in this game are fake. Only attack this sandbox.</p>
      </div>
    </section>`;
  view.querySelector("#name").focus();
  view.querySelector("#join-form").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const me = await api("/api/join", {
        method: "POST",
        body: { name: view.querySelector("#name").value, team: view.querySelector("#team").value || "Solo" },
      });
      setToken(me.token);
      sfx.win();
      location.hash = "#/map";
    } catch (err) {
      toast(err.message, "bad");
    }
  };
}
