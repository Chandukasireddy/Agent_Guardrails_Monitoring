// A level: guard card, chat, live pipeline, tripwire meter, flag box, and traces.

import { api, esc } from "../api.js";
import { refreshHeader } from "../app.js";
import { confetti, sfx, sleep, toast } from "../fx.js";

const KIND_ICON = { guardrail: "🛡️", generation: "🧠", tool: "🔧", agent: "🕵️", span: "•" };

export async function renderPlay(view, levelId) {
  let level;
  try {
    level = await api(`/api/levels/${levelId}`);
  } catch (e) {
    toast(e.message, "bad");
    location.hash = "#/map";
    return;
  }
  if (!level.unlocked) {
    toast("Locked. Crack the previous vault first.", "bad");
    location.hash = "#/map";
    return;
  }
  const c = level.character;
  view.innerHTML = `
    <div class="play" style="--c:${esc(c.color)}">
      <aside class="side">
        <div class="panel guard-card" id="guard-card">
          <div class="big-avatar" id="avatar">${esc(c.avatar)}</div>
          <h2>${esc(c.name)}</h2>
          <div class="tagline">“${esc(c.tagline)}”</div>
        </div>
        <div class="panel">
          <h3>Mission · ${esc(level.title)}</h3>
          <div class="briefing">${esc(level.briefing)}</div>
        </div>
        <div class="panel">
          <h3>Defenses on this level</h3>
          <div class="rail-list" id="rail-list"></div>
        </div>
        <div class="panel">
          <h3>Crack the vault</h3>
          <form class="flag-form" id="flag-form">
            <input class="field mono" id="flag" placeholder="FAKE-..." autocomplete="off" />
            <button class="btn primary" type="submit">Submit flag</button>
          </form>
          <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn small" id="hint-btn">💡 Hint (${level.hints.length}/${level.hints_total})</button>
            ${level.solved ? `<button class="btn small" id="lesson-btn">📖 Lesson</button>` : ""}
          </div>
          <div id="hints"></div>
        </div>
      </aside>

      <section class="panel chat">
        <div class="chat-head">
          <span style="font-size:22px">${esc(c.avatar)}</span>
          <span class="title">${esc(c.name)}</span>
          ${level.solved ? `<span class="pill" style="color:var(--ok)">✓ cracked</span>` : ""}
          <span class="spacer" style="flex:1"></span>
          <span class="pill">attempts <b id="attempts">${level.attempts}</b></span>
          <button class="btn small" id="reset-btn" title="Start a fresh conversation">↺ Reset chat</button>
          <a class="btn small" href="#/map">← Map</a>
        </div>
        <div class="messages" id="messages"></div>
        <form class="composer" id="composer">
          <textarea class="field" id="input" placeholder="Talk to ${esc(c.name)}… (Enter to send, Shift+Enter for a new line)"></textarea>
          <button class="btn primary" type="submit">Send</button>
        </form>
      </section>

      <aside class="side">
        <div class="panel">
          <h3>Live pipeline</h3>
          <div class="pipeline" id="pipeline"></div>
        </div>
        <div class="panel">
          <h3>Tripwire</h3>
          <div class="meter"><div id="meter"></div></div>
          <div class="meter-label"><span>calm</span><span id="meter-text">0%</span><span>alarm</span></div>
        </div>
        <div class="panel">
          <h3>Observability</h3>
          <div class="muted" style="font-size:13px" id="trace-info">Send a message, then open its trace to see every step.</div>
          <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn small" id="trace-btn" disabled>🔍 Open last trace</button>
            <a class="btn small hidden" id="langfuse-link" target="_blank">📡 Langfuse</a>
          </div>
        </div>
      </aside>
    </div>`;

  const $ = (sel) => view.querySelector(sel);
  const messages = $("#messages");
  let lastTrace = null;

  // --- defenses list ---------------------------------------------------
  const chips = [];
  for (const [stage, rails] of Object.entries(level.rails)) {
    for (const r of rails) chips.push(`<div class="rail-chip"><span class="tag ${stage}">${stage}</span><div><b class="mono">${esc(r.name)}</b><br><span class="muted">${esc(r.description)}</span></div></div>`);
  }
  for (const t of level.tools) chips.push(`<div class="rail-chip"><span class="tag toolname">tool</span><div><b class="mono">${esc(t)}</b><br><span class="muted">The guard can call this.</span></div></div>`);
  $("#rail-list").innerHTML = chips.join("") || `<div class="muted">None. The door is wide open.</div>`;

  // --- pipeline --------------------------------------------------------
  function buildPipeline() {
    const parts = [];
    const node = (key, label, icon) => `<div class="node" data-key="${esc(key)}"><span class="lbl">${icon} ${esc(label)}</span><span class="st"></span></div>`;
    const group = (t) => `<div class="node group">${t}</div>`;
    const conn = `<div class="connector"></div>`;
    parts.push(node("you", "your message", "💬"));
    if (level.rails.input.length) { parts.push(conn, group("input rails")); level.rails.input.forEach((r) => parts.push(node(`input:${r.name}`, r.name, "🛡️"))); }
    parts.push(conn, node("guard", c.name, "🧠"));
    if (level.tools.length) {
      parts.push(conn, group("tools"));
      level.rails.tool.forEach((r) => parts.push(node(`tool:${r.name}`, r.name, "🛡️")));
      level.tools.forEach((t) => parts.push(node(`toolcall:${t}`, t, "🔧")));
    }
    if (level.rails.output.length) { parts.push(conn, group("output rails")); level.rails.output.forEach((r) => parts.push(node(`output:${r.name}`, r.name, "🛡️"))); }
    parts.push(conn, node("reply", "reply to you", "📨"));
    $("#pipeline").innerHTML = parts.join("");
  }
  buildPipeline();

  function setNode(key, status, reason = "") {
    const el = $(`#pipeline .node[data-key="${CSS.escape(key)}"]`);
    if (!el) return null;
    el.classList.remove("pass", "block", "active", "skip");
    el.classList.add(status);
    el.querySelector(".st").textContent = { pass: "✓ pass", block: "✕ block", active: "…" }[status] || "";
    el.querySelector(".reason")?.remove();
    if (reason && status === "block") el.insertAdjacentHTML("beforeend", `<span class="reason">${esc(reason)}</span>`);
    let prev = el.previousElementSibling;
    while (prev && !prev.classList.contains("connector")) prev = prev.previousElementSibling;
    prev?.classList.add("lit");
    return el;
  }

  async function animate(events, finalStatus) {
    $("#pipeline").querySelectorAll(".node:not(.group)").forEach((n) => { n.classList.remove("pass", "block", "active"); n.classList.add("skip"); n.querySelector(".st").textContent = ""; n.querySelector(".reason")?.remove(); });
    $("#pipeline").querySelectorAll(".connector").forEach((n) => n.classList.remove("lit"));
    setNode("you", "pass");
    for (const ev of events) {
      await sleep(230);
      let key = `${ev.stage}:${ev.name}`;
      if (ev.stage === "guard") key = "guard";
      if (ev.stage === "tool" && ev.args) key = `toolcall:${ev.name}`;
      const status = ev.status === "block" || ev.status === "error" ? "block" : "pass";
      setNode(key, status, ev.reason);
      status === "block" ? sfx.block() : sfx.pass();
    }
    await sleep(230);
    setNode("reply", finalStatus === "ok" ? "pass" : "block");
  }

  // --- chat ------------------------------------------------------------
  function addMessage(role, text, extra = {}) {
    messages.querySelector(".empty-chat")?.remove();
    const el = document.createElement("div");
    el.className = `msg ${role === "user" ? "user" : "guard"} ${extra.status === "blocked" ? "blocked" : ""} ${extra.status === "error" ? "error" : ""}`;
    el.innerHTML = (role === "user" ? "" : `<div class="who">${esc(c.avatar)} ${esc(c.name)}</div>`) + `<div class="body"></div>`;
    el.querySelector(".body").textContent = text;
    if (extra.status === "blocked") el.insertAdjacentHTML("beforeend", `<div class="badge">BLOCKED by ${esc(extra.blocked_by)}${extra.reason ? ": " + esc(extra.reason) : ""}</div>`);
    if (extra.leak) el.insertAdjacentHTML("beforeend", `<div class="badge leak">✨ Something shiny slipped out. Submit it!</div>`);
    if (extra.trace_id) {
      const b = document.createElement("button");
      b.className = "trace-btn"; b.title = "Open the trace for this reply"; b.textContent = "🔍";
      b.onclick = () => openTrace(extra.trace_id);
      el.appendChild(b);
    }
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
  }

  if (level.history.length) level.history.forEach((m) => addMessage(m.role, m.content));
  else messages.innerHTML = `<div class="empty-chat"><div class="big">${esc(c.avatar)}</div><p>${esc(c.name)} is waiting. Say hello, or start your heist.</p></div>`;
  setMeter(level.meter || 0);

  function setMeter(v) {
    $("#meter").style.width = `${Math.round(v * 100)}%`;
    $("#meter-text").textContent = `${Math.round(v * 100)}%`;
  }

  async function send(text) {
    addMessage("user", text);
    sfx.send();
    const typing = document.createElement("div");
    typing.className = "typing";
    typing.innerHTML = `${esc(c.name)} is thinking<span>.</span><span>.</span><span>.</span>`;
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;
    try {
      const r = await api(`/api/levels/${levelId}/chat`, { method: "POST", body: { message: text } });
      typing.remove();
      await animate(r.events, r.status);
      addMessage("guard", r.reply, r);
      setMeter(r.meter);
      $("#attempts").textContent = Number($("#attempts").textContent) + 1;
      lastTrace = r.trace_id;
      $("#trace-btn").disabled = false;
      $("#trace-info").textContent = `Last turn: ${r.events.length} steps · status ${r.status}`;
      const lf = $("#langfuse-link");
      if (r.langfuse_url) { lf.href = r.langfuse_url; lf.classList.remove("hidden"); }
      if (r.status === "blocked") {
        $("#avatar").classList.remove("shake"); void $("#avatar").offsetWidth; $("#avatar").classList.add("shake");
        $("#guard-card").classList.remove("blocked-flash"); void $("#guard-card").offsetWidth; $("#guard-card").classList.add("blocked-flash");
      }
      if (r.leak) sfx.leak();
    } catch (e) {
      typing.remove();
      addMessage("guard", e.message, { status: "error" });
    }
  }

  $("#trace-btn").onclick = () => lastTrace && openTrace(lastTrace);

  const input = $("#input");
  $("#composer").onsubmit = (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    send(text);
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); }
  });
  input.focus();

  $("#reset-btn").onclick = async () => {
    await api(`/api/levels/${levelId}/reset`, { method: "POST" });
    messages.innerHTML = "";
    setMeter(0);
    buildPipeline();
    toast("Fresh start. The guard forgot everything.");
  };

  // --- hints & flag ----------------------------------------------------
  const renderHints = (hints) => ($("#hints").innerHTML = hints.map((h) => `<div class="hint">💡 ${esc(h)}</div>`).join(""));
  renderHints(level.hints);
  $("#hint-btn").onclick = async () => {
    const r = await api(`/api/levels/${levelId}/hint`, { method: "POST" });
    renderHints(r.hints);
    $("#hint-btn").textContent = `💡 Hint (${r.hints.length}/${r.total})`;
  };
  $("#lesson-btn")?.addEventListener("click", () => showCracked(level, null));

  $("#flag-form").onsubmit = async (e) => {
    e.preventDefault();
    const flag = $("#flag").value.trim();
    if (!flag) return;
    const r = await api(`/api/levels/${levelId}/flag`, { method: "POST", body: { flag } });
    if (!r.correct) { sfx.wrong(); toast(r.message, "bad"); return; }
    sfx.win();
    confetti();
    showCracked(r.level, r);
    refreshHeader();
  };
}

function showCracked(level, result) {
  const reveal = level.reveal || {};
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `
    <div class="modal cracked">
      <button class="close">×</button>
      <h1>${result ? "VAULT CRACKED" : esc(level.title)}</h1>
      <div class="pts">${result ? (result.first_time ? `+${result.points} points` : esc(result.message)) : "Lesson review"}</div>
      <div class="lesson-grid">
        <div class="lesson-card attack"><h4>⚔️ What worked</h4><div>${esc(level.lesson?.attack)}</div></div>
        <div class="lesson-card defense"><h4>🛡️ How to defend</h4><div>${esc(level.lesson?.defense)}</div></div>
      </div>
      <h3 style="margin-top:18px" class="muted">Behind the curtain</h3>
      <div class="muted" style="font-size:13px">The guard's system prompt (authz: <span class="mono">${esc(reveal.authz)}</span>, file: <span class="mono">${esc(reveal.source)}</span>):</div>
      <pre class="code">${esc(reveal.system_prompt)}</pre>
      <div class="muted" style="font-size:13px">Rails and their settings:</div>
      <pre class="code">${esc(JSON.stringify(reveal.rails, null, 2))}</pre>
      <div style="display:flex;gap:10px;justify-content:center;margin-top:16px">
        <a class="btn primary" href="#/map">Next vault →</a>
      </div>
    </div>`;
  ov.querySelector(".close").onclick = () => ov.remove();
  ov.querySelector("a").onclick = () => ov.remove();
  ov.onclick = (e) => { if (e.target === ov) ov.remove(); };
  document.body.appendChild(ov);
}

async function openTrace(traceId) {
  let t;
  try { t = await api(`/api/traces/${traceId}`); } catch (e) { toast(e.message, "bad"); return; }
  const short = (v) => {
    const s = typeof v === "string" ? v : JSON.stringify(v);
    return s && s.length > 400 ? s.slice(0, 400) + "…" : s ?? "";
  };
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `
    <div class="modal">
      <button class="close">×</button>
      <h2 style="margin-top:0">🔍 Trace <span class="mono muted" style="font-size:14px">${esc(t.id)}</span></h2>
      <div class="muted" style="margin-bottom:12px">Status <b>${esc(t.status)}</b> · ${t.spans.length} spans ·
        ${t.langfuse_url ? `<a href="${esc(t.langfuse_url)}" target="_blank">open in Langfuse</a>` : "local trace (set Langfuse keys in .env to mirror traces)"}</div>
      ${t.spans.map((s) => `
        <div class="span-row ${esc(s.status)}">
          <span>${KIND_ICON[s.kind] || "•"}</span>
          <span><b class="name mono">${esc(s.name)}</b> <span class="k">${esc(s.kind)}</span> <span class="muted">${esc(s.status)}</span></span>
          <span class="mono muted">${s.ms} ms</span>
          <div class="io">in:  ${esc(short(s.input))}\nout: ${esc(short(s.output))}${s.meta && s.meta.model ? `\nmodel: ${esc(s.meta.model)}` : ""}</div>
        </div>`).join("")}
    </div>`;
  ov.querySelector(".close").onclick = () => ov.remove();
  ov.onclick = (e) => { if (e.target === ov) ov.remove(); };
  document.body.appendChild(ov);
}
