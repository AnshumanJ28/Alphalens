// ALL backend calls live here — matched against backend/main.py.
import { createClient } from "@supabase/supabase-js";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const MOCK = import.meta.env.VITE_USE_MOCK !== "false";

// Auth goes through Supabase directly (publishable key only — never the
// secret key). The session's access_token is sent to FastAPI as a Bearer
// token, which backend/auth.py's get_current_user verifies.
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

const token = () => localStorage.getItem("al_token"); // mock-mode fallback only

async function authToken() {
  return "mock_token";
}

async function call(path, opts = {}) {
  const t = await authToken();
  const res = await fetch(BASE + path, {
    ...opts,
    headers: { "Content-Type": "application/json", ...(t && { Authorization: `Bearer ${t}` }) },
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const data = await res.clone().json();
      if (data.detail) msg = data.detail;
    } catch {
      const text = await res.text().catch(() => "");
      if (text) msg = text;
    }
    throw new Error(msg);
  }
  return res;
}
const postJSON = async (path, body) => (await call(path, { method: "POST", body: JSON.stringify(body) })).json();
const getJSON = async (path) => (await call(path)).json();

// ---- Mock helpers (used only when VITE_USE_MOCK is not "false") ----
const hist = () => JSON.parse(localStorage.getItem("al_hist") || "[]");
const started = {};
const MOCK_ORDER = ["PENDING", "PROCESSING", "COMPLETED"];
const mockSnapshot = (ticker) => ({
  company: ticker,
  summary: "Balance sheet is sturdy and margins are steady. News tone is mostly positive, with some caution on guidance.",
  ratios: [
    { name: "P/E", value: "24.3", status: "watch" },
    { name: "EPS", value: "62.1", status: "healthy" },
    { name: "P/B", value: "7.9", status: "watch" },
    { name: "Debt to equity", value: "0.08", status: "healthy" },
    { name: "Current ratio", value: "2.4", status: "healthy" },
    { name: "Net margin", value: "17.6%", status: "healthy" },
  ],
  sentiment: { positive: 58, neutral: 30, negative: 12, label: "Positive" },
  peer: { ticker: "WIPRO.NS", rows: [
    { metric: "P/E", target: "24.3", peer: "19.8" },
    { metric: "Net margin", target: "17.6%", peer: "12.1%" },
    { metric: "Debt to equity", target: "0.08", peer: "0.21" },
  ] },
});

// ---- Public API ----
export async function isAuthed() {
  return true;
}
export async function logout() {
  if (MOCK) return localStorage.removeItem("al_token");
  await supabase.auth.signOut();
}

// mode: "login" | "signup"
export async function auth(mode, email, password) {
  if (MOCK) { localStorage.setItem("al_token", "mock"); return; }
  const { data, error } =
    mode === "login"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
  if (!data.session) throw new Error("Please confirm your email address to log in!");
}

// POST /api/search {ticker} -> 202 {task_id}
export async function startResearch(ticker) {
  if (!MOCK) return postJSON("/api/search", { ticker });
  const id = crypto.randomUUID();
  started[id] = Date.now();
  localStorage.setItem("al_hist", JSON.stringify([{ id, ticker, at: new Date().toISOString() }, ...hist()]));
  return { task_id: id };
}

// Document upload: NOT in backend/main.py yet — this calls a guessed
// POST /api/upload (multipart, field name "file") that returns {task_id},
// same shape as /api/search. Ask your teammate to add this route; until
// then real mode will 404 here, and mock mode fakes the whole flow.
export async function startResearchFromFile(file) {
  if (!MOCK) {
    const t = await authToken();
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(BASE + "/api/upload", {
      method: "POST",
      headers: { ...(t && { Authorization: `Bearer ${t}` }) }, // no Content-Type: browser sets the multipart boundary
      body: form,
    });
    if (!res.ok) throw new Error((await res.text().catch(() => "")) || res.statusText);
    return res.json();
  }
  const id = crypto.randomUUID();
  started[id] = Date.now();
  const label = file.name.replace(/\.[^.]+$/, "").toUpperCase();
  localStorage.setItem("al_hist", JSON.stringify([{ id, ticker: label, at: new Date().toISOString() }, ...hist()]));
  return { task_id: id };
}

// GET /api/status/{task_id} -> {task_id, status: PENDING|PROCESSING|COMPLETED|FAILED, error}
export async function getStatus(id) {
  if (!MOCK) return getJSON(`/api/status/${id}`);
  const i = Math.min(Math.floor((Date.now() - (started[id] || 0)) / 2500), 2);
  return { status: MOCK_ORDER[i] };
}

// GET /api/result/{task_id} -> the PDF bytes, one-shot: the backend deletes
// the task record and cleans up files as soon as this is read, so this can
// only be called once per finished task. There is no JSON snapshot endpoint
// (no ratios/sentiment/peer data), so real mode can only show the PDF.
export async function getResult(id) {
  const res = await call(`/api/result/${id}`);
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// GET /api/result-json/{task_id} -> JSON snapshot with ratios, sentiment, score
export async function getResultJSON(id) {
  return getJSON(`/api/result-json/${id}`);
}

export async function getSnapshot(ticker) {
  return mockSnapshot(ticker); // mock mode only — see getResult for real mode
}

// No history endpoint exists in backend/main.py yet (searches are logged via
// database.log_search, but nothing reads them back). Mock mode keeps a local
// list so the screen has something to show; real mode returns empty until
// that endpoint exists.
export async function getHistory() {
  return MOCK ? hist() : [];
}