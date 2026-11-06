// Small shared helpers: a sleep for animating the route, and a single toast for feedback.

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let toastTimer = null;
export function toast(message, tone = "info") {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const el = document.createElement("div");
  el.className = `toast ${tone}`;
  el.setAttribute("role", "status");
  el.textContent = message;
  document.body.appendChild(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 3200);
}
