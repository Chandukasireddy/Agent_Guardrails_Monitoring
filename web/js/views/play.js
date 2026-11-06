// One vault: the conversation with its guard, the route each message takes through the
// defenses, the flag box, and the trace behind every reply.

import { api, esc } from "../api.js";
import { refreshHeader } from "../app.js";
import { sleep, toast } from "../fx.js";
import { icon, hasIcon } from "../icons.js";

const KIND_LABEL = { guardrail: "Check", generation: "Model", tool: "Tool", agent: "Turn", span: "Step" };
const clock = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export async function renderPlay(view, levelId, setCrumbs) {
  let level;
  try {
    level = await api(`/api/levels/${levelId}`);
  } catch (e) {
    toast(e.message, "bad");
    location.hash = "#/map";
    return;
  }
  if (!level.unlocked) {
    toast("This vault is locked. Crack the one before it first.", "bad");
    location.hash = "#/map";
    return;
  }
  setCrumbs([{ label: "Vaults", href: "#/map" }, { label: level.title }]);
  const levels = await api("/api/levels").catch(() => []);
  const c = level.character;
  const railCount = ["input", "tool", "output"].reduce((n, k) => n + (level.rails[k] || []).length, 0);

  view.innerHTML = `
    <div class="workspace">
      <nav class="vault-nav" aria-label="Vaults">
        <div class="nav-label">Vaults</div>
        <ol>
          ${levels.map((l) => `
            <li>
              ${l.unlocked
                ? `<a href="#/play/${encodeURIComponent(l.id)}" class="${l.id === levelId ? "current" : ""}" ${l.id === levelId ? 'aria-current="page"' : ""}>
                     <span class="mono num">${String(l.order).padStart(2, "0")}</span>
                     <span class="nav-title">${esc(l.title)}</span>
                     <span class="nav-state ${l.solved ? "cracked" : ""}">${l.solved ? "Cracked" : ""}</span>
                   </a>`
                : `<span class="locked" aria-disabled="true"><span class="mono num">${String(l.order).padStart(2, "0")}</span><span class="nav-title">${esc(l.title)}</span><span class="nav-state">Locked</span></span>`}
            </li>`).join("")}
        </ol>
      </nav>

      <section class="conversation" aria-labelledby="guard-name">
        <header class="conv-head">
          <div class="guard-id">
            <span class="avatar" aria-hidden="true">${icon(hasIcon(c.avatar) ? c.avatar : "shield-check", 18)}</span>
            <div>
              <h1 id="guard-name">${esc(c.name)}</h1>
              <p class="muted">${esc(c.tagline)}</p>
            </div>
          </div>
          <div class="conv-meta">
            ${level.solved ? `<span class="badge cracked">Cracked</span>` : ""}
            <span class="stat"><span class="muted">Attempts</span> <b class="mono" id="attempts">${level.attempts}</b></span>
            <button class="btn small ghost" id="reset-btn" type="button">Reset chat</button>
          </div>
        </header>

        <div class="messages" id="messages" role="log" aria-live="polite" aria-label="Conversation with ${esc(c.name)}"></div>

        <form class="composer" id="composer">
          <label class="sr-only" for="input">Message ${esc(c.name)}</label>
          <textarea class="field" id="input" rows="2" maxlength="2000" placeholder="Message ${esc(c.name)}. Enter sends. Shift+Enter adds a line."></textarea>
          <button class="btn primary" type="submit" id="send-btn">Send</button>
        </form>
      </section>

      <aside class="inspector" aria-label="Vault details">
        <section class="panel">
          <h2 class="panel-title">Mission</h2>
          <p class="briefing">${esc(level.briefing)}</p>
        </section>

        <section class="panel" aria-labelledby="flag-title">
          <h2 class="panel-title" id="flag-title">Crack the vault</h2>
          <form id="flag-form" class="flag-form" novalidate>
            <label class="sr-only" for="flag">Secret you found</label>
            <input class="field mono" id="flag" autocomplete="off" spellcheck="false" placeholder="FAKE-…" />
            <button class="btn primary" type="submit">Submit</button>
          </form>
          <p class="field-error hidden" id="flag-error" role="alert"></p>
          <p class="small-print">The secret is in the guard's reply. Paste it here exactly as written.</p>
        </section>

        <section class="panel" aria-labelledby="route-title">
          <div class="panel-head">
            <h2 class="panel-title" id="route-title">Route</h2>
            <span class="muted small-print" id="route-note">Your next message will travel this route.</span>
          </div>
          <ol class="route" id="route" aria-live="polite"></ol>
        </section>

        <section class="panel">
          <h2 class="panel-title">Defenses on this vault</h2>
          <ul class="defenses" id="defenses"></ul>
        </section>

        <section class="panel">
          <h2 class="panel-title">Suspicion</h2>
          <div class="meter" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round((level.meter || 0) * 100)}" aria-label="Suspicion">
            <div id="meter"></div>
          </div>
          <div class="meter-label"><span>Calm</span><span class="mono" id="meter-text">${Math.round((level.meter || 0) * 100)}%</span><span>Alarmed</span></div>
          <p class="small-print">The guard grows more alarmed as messages look more like attacks.</p>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">Hints</h2>
            <button class="btn small ghost" type="button" id="hint-btn">Show hint <span class="mono" id="hint-count">(${level.hints.length}/${level.hints_total})</span></button>
          </div>
          <div id="hints" class="hints"></div>
        </section>

        <section class="panel">
          <h2 class="panel-title">Trace</h2>
          <p class="muted" id="trace-info">Send a message to record its trace.</p>
          <div class="panel-actions">
            <button class="btn small" id="trace-btn" type="button" disabled>Open last trace</button>
            <a class="btn small ghost hidden" id="langfuse-link" target="_blank" rel="noopener">Open in Langfuse</a>
          </div>
        </section>

        ${level.solved ? `<section class="panel"><button class="btn ghost wide" id="lesson-btn" type="button">Review the lesson</button></section>` : ""}
      </aside>
    </div>`;

  const $ = (sel) => view.querySelector(sel);
  const messages = $("#messages");
  let lastTrace = null;
  let busy = false;

  // --- defenses ----------------------------------------------------------
  const defs = [];
  for (const [stage, label] of [["input", "Input check"], ["tool", "Tool check"], ["output", "Output check"]]) {
    for (const r of level.rails[stage] || []) defs.push({ label, name: r.name, desc: r.description });
  }
  for (const t of level.tools) defs.push({ label: "Tool", name: t, desc: "The guard can call this tool." });
  $("#defenses").innerHTML = defs.length
    ? defs.map((d) => `<li><span class="kind">${esc(d.label)}</span><span><b class="mono">${esc(d.name)}</b><span class="muted">${esc(d.desc)}</span></span></li>`).join("")
    : `<li class="muted">No checks on this vault. Ask nicely, or try anything.</li>`;

  // --- route (the signature: each message travels these stations) -----
  const stations = [{ key: "you", label: "Your message" }];
  (level.rails.input || []).forEach((r) => stations.push({ key: `input:${r.name}`, label: r.name }));
  stations.push({ key: "guard", label: c.name });
  (level.rails.tool || []).forEach((r) => stations.push({ key: `tool:${r.name}`, label: r.name }));
  level.tools.forEach((t) => stations.push({ key: `toolcall:${t}`, label: t }));
  (level.rails.output || []).forEach((r) => stations.push({ key: `output:${r.name}`, label: r.name }));
  stations.push({ key: "reply", label: "Reply to you" });

  function drawRoute() {
    $("#route").innerHTML = stations.map((s) => `
      <li class="station" data-key="${esc(s.key)}">
        <span class="pip" aria-hidden="true"></span>
        <span class="station-label">${esc(s.label)}</span>
        <span class="station-state"></span>
      </li>`).join("");
  }
  drawRoute();

  function setStation(key, status, reason = "") {
    const el = view.querySelector(`#route .station[data-key="${CSS.escape(key)}"]`);
    if (!el) return;
    el.className = `station ${status}`;
    el.querySelector(".station-state").textContent = { pass: "Passed", block: "Blocked", active: "Checking" }[status] || "";
    el.title = reason;
    let note = el.querySelector(".station-reason");
    if (reason && status === "block") {
      if (!note) { note = document.createElement("span"); note.className = "station-reason"; el.appendChild(note); }
      note.textContent = reason;
    } else note?.remove();
  }

  async function animateRoute(events, finalStatus) {
    drawRoute();
    $("#route-note").textContent = "Last message";
    setStation("you", "pass");
    for (const ev of events) {
      setStation(keyFor(ev), "active");
      await sleep(260);
      setStation(keyFor(ev), ev.status === "block" || ev.status === "error" ? "block" : "pass", ev.reason || "");
    }
    setStation("reply", finalStatus === "ok" ? "pass" : "block");
  }
  const keyFor = (ev) => {
    if (ev.stage === "guard") return "guard";
    if (ev.stage === "tool" && ev.args) return `toolcall:${ev.name}`;
    return `${ev.stage}:${ev.name}`;
  };

  // --- conversation ------------------------------------------------------
  function addMessage(role, text, extra = {}) {
    messages.querySelector(".empty")?.remove();
    const el = document.createElement("article");
    el.className = `msg ${role}${extra.status === "blocked" ? " blocked" : ""}${extra.status === "error" ? " error" : ""}`;
    const who = role === "user" ? "You" : c.name;
    el.innerHTML = `
      <header class="msg-head"><span>${esc(who)}</span><time>${esc(extra.time || clock())}</time></header>
      <p class="msg-body"></p>`;
    el.querySelector(".msg-body").textContent = text;
    if (extra.status === "blocked") {
      el.insertAdjacentHTML("beforeend", `<p class="msg-note block-note">Stopped by <b class="mono">${esc(extra.blocked_by)}</b>${extra.reason ? `: ${esc(extra.reason)}` : ""}</p>`);
    }
    if (extra.leak) {
      el.insertAdjacentHTML("beforeend", `<div class="msg-note leak-note"><span>The secret is in this reply.</span><button type="button" class="btn small primary use-code">Use this code</button></div>`);
      el.querySelector(".use-code").onclick = () => {
        const flag = $("#flag");
        flag.value = extra.leak;
        flag.focus();
        toast("Code copied into the vault box. Submit it to crack the vault.");
      };
    }
    if (extra.trace_id) {
      el.appendChild(feedbackBar(extra.trace_id));
      const b = document.createElement("button");
      b.type = "button"; b.className = "trace-link"; b.textContent = "View trace";
      b.onclick = () => openTrace(extra.trace_id);
      el.appendChild(b);
    }
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
  }

  // Thumbs and an optional note on each reply. Saved to the local database and to Langfuse.
  function feedbackBar(traceId) {
    const bar = document.createElement("div");
    bar.className = "feedback";
    bar.innerHTML = `
      <div class="fb-row">
        <span class="fb-label">Was this reply right?</span>
        <button type="button" class="fb-btn" data-vote="1" aria-label="Thumbs up" aria-pressed="false">${icon("thumbs-up", 15)}</button>
        <button type="button" class="fb-btn" data-vote="-1" aria-label="Thumbs down" aria-pressed="false">${icon("thumbs-down", 15)}</button>
        <button type="button" class="fb-note-open">${icon("message-square", 14)}<span>Add a note</span></button>
        <span class="fb-status" aria-live="polite"></span>
      </div>
      <form class="fb-note hidden">
        <label class="sr-only">Note about how the guard behaved</label>
        <textarea class="field" rows="2" maxlength="1000" placeholder="How did the guard behave? For example: it stayed on topic, or it gave in too easily."></textarea>
        <div class="fb-note-actions">
          <button type="button" class="btn small ghost fb-cancel">Cancel</button>
          <button type="submit" class="btn small">Save note</button>
        </div>
      </form>`;
    let vote = 0;
    let note = "";
    const status = bar.querySelector(".fb-status");
    const noteForm = bar.querySelector(".fb-note");
    const textarea = noteForm.querySelector("textarea");
    const paint = () => bar.querySelectorAll("[data-vote]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.vote) === vote)));
    async function save(nextVote, nextNote) {
      try {
        await api("/api/feedback", { method: "POST", body: { trace_id: traceId, vote: nextVote, comment: nextNote } });
        vote = nextVote; note = nextNote;
        paint();
        status.textContent = "Saved";
      } catch (e) {
        status.textContent = "";
        toast(e.message, "bad");
      }
    }
    bar.querySelectorAll("[data-vote]").forEach((b) => (b.onclick = () => save(Number(b.dataset.vote), note)));
    bar.querySelector(".fb-note-open").onclick = () => { noteForm.classList.remove("hidden"); textarea.focus(); };
    noteForm.querySelector(".fb-cancel").onclick = () => noteForm.classList.add("hidden");
    noteForm.onsubmit = (e) => {
      e.preventDefault();
      const text = textarea.value.trim();
      if (!text) return;
      save(vote || 1, text).then(() => { noteForm.classList.add("hidden"); textarea.value = ""; });
    };
    return bar;
  }

  if (level.history.length) level.history.forEach((m) => addMessage(m.role === "user" ? "user" : "guard", m.content));
  else showEmpty();

  function showEmpty() {
    const starters = level.starters || [];
    messages.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon" aria-hidden="true">${icon(hasIcon(c.avatar) ? c.avatar : "shield-check", 22)}</span>
        <h2>${esc(c.name)} is listening</h2>
        <p class="muted">${esc(level.briefing)}</p>
        ${starters.length ? `<p class="small-print try-label">Try one of these, or write your own:</p>
        <div class="chips">${starters.map((t) => `<button type="button" class="chip" data-starter="${esc(t)}">${esc(t)}</button>`).join("")}</div>` : ""}
      </div>`;
    messages.querySelectorAll(".chip").forEach((chip) => {
      chip.onclick = () => { input.value = chip.dataset.starter; $("#composer").requestSubmit(); };
    });
  }

  function setMeter(v) {
    const pct = Math.round(v * 100);
    $("#meter").style.width = `${pct}%`;
    $("#meter-text").textContent = `${pct}%`;
    view.querySelector(".meter").setAttribute("aria-valuenow", String(pct));
  }
  setMeter(level.meter || 0);

  async function send() {
    const input = $("#input");
    const text = input.value.trim();
    if (!text || busy) return;
    busy = true;
    input.value = "";
    $("#send-btn").disabled = true;
    addMessage("user", text);
    const typing = document.createElement("div");
    typing.className = "typing";
    typing.textContent = `${c.name} is replying…`;
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;
    try {
      const r = await api(`/api/levels/${levelId}/chat`, { method: "POST", body: { message: text } });
      typing.remove();
      await animateRoute(r.events, r.status);
      const leak = r.leak ? extractFlag(r.reply) : "";
      addMessage("guard", r.reply, { ...r, leak });
      setMeter(r.meter);
      $("#attempts").textContent = Number($("#attempts").textContent) + 1;
      lastTrace = r.trace_id;
      $("#trace-btn").disabled = false;
      $("#trace-info").textContent = `Last turn: ${r.events.length} steps, ${r.status}.`;
      const lf = $("#langfuse-link");
      if (r.langfuse_url) { lf.href = r.langfuse_url; lf.classList.remove("hidden"); }
    } catch (e) {
      typing.remove();
      addMessage("guard", e.message, { status: "error" });
      drawRoute();
    } finally {
      busy = false;
      $("#send-btn").disabled = false;
      input.focus();
    }
  }
  // The leak check says the secret is in the reply; find the FAKE- code itself to offer it.
  const extractFlag = (text) => (text.match(/FAKE-[A-Z0-9-]+/) || [""])[0];

  const input = $("#input");
  $("#composer").onsubmit = (e) => { e.preventDefault(); send(); };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("#composer").requestSubmit(); }
  });
  input.focus();

  $("#reset-btn").onclick = async () => {
    if (!confirm("Start a fresh conversation with this guard? The attempts count stays.")) return;
    await api(`/api/levels/${levelId}/reset`, { method: "POST" });
    messages.innerHTML = "";
    showEmpty();
    setMeter(0);
    drawRoute();
  };

  // --- hints -----------------------------------------------------------
  const renderHints = (hints) => ($("#hints").innerHTML = hints.map((h) => `<p class="hint">${esc(h)}</p>`).join(""));
  renderHints(level.hints);
  $("#hint-btn").onclick = async () => {
    const r = await api(`/api/levels/${levelId}/hint`, { method: "POST" });
    renderHints(r.hints);
    $("#hint-count").textContent = `(${r.hints.length}/${r.total})`;
    if (r.hints.length >= r.total) $("#hint-btn").disabled = true;
  };

  // --- flag ------------------------------------------------------------
  $("#flag-form").onsubmit = async (e) => {
    e.preventDefault();
    const flagInput = $("#flag");
    const flag = flagInput.value.trim();
    const err = $("#flag-error");
    if (!flag) {
      err.textContent = "Paste the secret from the guard's reply first.";
      err.classList.remove("hidden");
      flagInput.focus();
      return;
    }
    const r = await api(`/api/levels/${levelId}/flag`, { method: "POST", body: { flag } });
    if (!r.correct) {
      err.textContent = r.message;
      err.classList.remove("hidden");
      flagInput.setAttribute("aria-invalid", "true");
      flagInput.focus();
      return;
    }
    err.classList.add("hidden");
    flagInput.removeAttribute("aria-invalid");
    refreshHeader();
    showCracked(r.level, r);
  };
  $("#flag").addEventListener("input", () => {
    $("#flag").removeAttribute("aria-invalid");
    $("#flag-error").classList.add("hidden");
  });

  $("#trace-btn").onclick = () => lastTrace && openTrace(lastTrace);
  $("#lesson-btn")?.addEventListener("click", () => showCracked(level, null));
  if (railCount === 0) $("#route-note").textContent = "No checks here. Every message goes straight to the guard.";
}

// --- dialogs -------------------------------------------------------------
function openDialog(html) {
  const dlg = document.createElement("dialog");
  dlg.className = "dialog";
  dlg.innerHTML = html;
  dlg.addEventListener("close", () => dlg.remove());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  dlg.querySelector("[data-close]")?.addEventListener("click", () => dlg.close());
  document.body.appendChild(dlg);
  dlg.showModal();
  return dlg;
}

function showCracked(level, result) {
  const reveal = level.reveal || {};
  const title = result ? (result.first_time ? "Vault cracked" : "Already cracked") : "Lesson";
  openDialog(`
    <header class="dialog-head">
      <div><p class="eyebrow">${esc(title)}</p><h2>${esc(level.title)}</h2>
        <p class="muted">${result ? (result.first_time ? `+${result.points} points` : esc(result.message)) : esc(level.subtitle || "")}</p></div>
      <button class="icon-btn" type="button" data-close aria-label="Close">×</button>
    </header>
    <div class="lesson-grid">
      <section><h3>What worked</h3><p>${esc(level.lesson?.attack)}</p></section>
      <section><h3>How to defend</h3><p>${esc(level.lesson?.defense)}</p></section>
    </div>
    <details class="behind">
      <summary>Behind the curtain</summary>
      <p class="small-print">System prompt (authz <span class="mono">${esc(reveal.authz)}</span>, file <span class="mono">${esc(reveal.source)}</span>)</p>
      <pre class="code">${esc(reveal.system_prompt)}</pre>
      <p class="small-print">Checks and their settings</p>
      <pre class="code">${esc(JSON.stringify(reveal.rails, null, 2))}</pre>
    </details>
    <footer class="dialog-foot">
      <a class="btn primary" href="#/map" data-close>Back to vaults</a>
    </footer>`);
}

async function openTrace(traceId) {
  let t;
  try { t = await api(`/api/traces/${traceId}`); } catch (e) { toast(e.message, "bad"); return; }
  const short = (v) => {
    const s = typeof v === "string" ? v : JSON.stringify(v);
    return s && s.length > 400 ? s.slice(0, 400) + "…" : s ?? "";
  };
  openDialog(`
    <header class="dialog-head">
      <div><p class="eyebrow">Trace</p><h2 class="mono trace-id">${esc(t.id)}</h2>
        <p class="muted">Status <b>${esc(t.status)}</b> · ${t.spans.length} steps ·
          ${t.langfuse_url ? `<a href="${esc(t.langfuse_url)}" target="_blank" rel="noopener">Open in Langfuse</a>` : "local only (add Langfuse keys to .env to send it there)"}</p></div>
      <button class="icon-btn" type="button" data-close aria-label="Close">×</button>
    </header>
    <ol class="steps">
      ${t.spans.map((s) => `
        <li class="step ${esc(s.status)}">
          <div class="step-head"><b class="mono">${esc(s.name)}</b><span class="muted">${esc(KIND_LABEL[s.kind] || s.kind)} · ${esc(s.status)} · ${s.ms} ms</span></div>
          <pre class="io">in   ${esc(short(s.input))}
out  ${esc(short(s.output))}${s.meta && s.meta.model ? `\nmodel ${esc(s.meta.model)}` : ""}</pre>
        </li>`).join("")}
    </ol>`);
}
