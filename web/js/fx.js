// Sound effects (generated with WebAudio, no files needed), confetti, and toasts.

let ctx = null;
let muted = false;
try { muted = localStorage.getItem("vaultheist.muted") === "1"; } catch { /* ignore */ }

export const isMuted = () => muted;
export function toggleMute() {
  muted = !muted;
  try { localStorage.setItem("vaultheist.muted", muted ? "1" : "0"); } catch { /* ignore */ }
  return muted;
}

function tone(freq, start, dur, type = "sine", gain = 0.06) {
  if (muted) return;
  ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.value = freq;
  g.gain.setValueAtTime(gain, ctx.currentTime + start);
  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + dur);
  o.connect(g).connect(ctx.destination);
  o.start(ctx.currentTime + start);
  o.stop(ctx.currentTime + start + dur + 0.02);
}

export const sfx = {
  send: () => tone(660, 0, 0.08, "triangle"),
  pass: () => tone(880, 0, 0.06, "sine", 0.03),
  block: () => { tone(140, 0, 0.25, "sawtooth", 0.07); tone(110, 0.12, 0.3, "sawtooth", 0.06); },
  leak: () => [523, 659, 784].forEach((f, i) => tone(f, i * 0.08, 0.15, "triangle")),
  win: () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, i * 0.1, 0.3, "triangle", 0.07)),
  wrong: () => tone(220, 0, 0.3, "square", 0.04),
};

export function toast(text, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

export function confetti(ms = 3500) {
  const canvas = document.getElementById("confetti");
  const c = canvas.getContext("2d");
  canvas.classList.remove("hidden");
  canvas.width = innerWidth;
  canvas.height = innerHeight;
  const colors = ["#38bdf8", "#a78bfa", "#4ade80", "#facc15", "#f43f5e"];
  const bits = Array.from({ length: 180 }, () => ({
    x: Math.random() * canvas.width, y: -20 - Math.random() * canvas.height * 0.5,
    vx: (Math.random() - 0.5) * 4, vy: 2 + Math.random() * 4, r: Math.random() * Math.PI,
    s: 6 + Math.random() * 6, color: colors[Math.floor(Math.random() * colors.length)],
  }));
  const end = performance.now() + ms;
  (function frame(t) {
    c.clearRect(0, 0, canvas.width, canvas.height);
    for (const b of bits) {
      b.x += b.vx; b.y += b.vy; b.r += 0.1; b.vy += 0.03;
      c.save(); c.translate(b.x, b.y); c.rotate(b.r); c.fillStyle = b.color;
      c.fillRect(-b.s / 2, -b.s / 4, b.s, b.s / 2); c.restore();
    }
    if (t < end) requestAnimationFrame(frame);
    else canvas.classList.add("hidden");
  })(performance.now());
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
