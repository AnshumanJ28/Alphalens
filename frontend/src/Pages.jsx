import { useEffect, useState } from "react";
import * as api from "./api";

const MOCK = import.meta.env.VITE_USE_MOCK !== "false";
const STAGE_INFO = {
  PENDING: { name: "Queued", note: "Waiting for a worker", color: "var(--mute)" },
  PROCESSING: { name: "Researching", note: "Gathering data and crunching numbers", color: "var(--lilac)" },
  COMPLETED: { name: "Done", note: "Your report is ready", color: "var(--chrome-done)" },
};

export function Home({ go, authed }) {
  const [ticker, setTicker] = useState("");
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!authed) return go("login");
    try {
      const t = ticker.trim().toUpperCase();
      const { task_id } = await api.startResearch(t);
      go("report", { id: task_id, ticker: t });
    } catch (x) { setErr(x.message); }
  }

  return (
    <section className="hero">
      <h1 className="hero-h1">
        <span>Find your</span>
        <span className="accent">edge</span>
        <span>before the market does.</span>
      </h1>
      <p className="lede">Enter a ticker. Alphalens reads the filings and the news, works out the ratios, and hands you a cited report.</p>
      <form onSubmit={submit} className="search">
        <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="INFY.NS" aria-label="Stock ticker" required />
        <button className="cta">{authed ? "Run research" : "Log in to run research"}</button>
      </form>
      {err && <p className="error" role="alert">{err}</p>}
      <ol className="stages">
        {Object.entries(STAGE_INFO).map(([key, s]) => (
          <li key={key} style={{ "--c": s.color }}><b>{s.name}</b><span>{s.note}</span></li>
        ))}
      </ol>
    </section>
  );
}

export function Report({ id, ticker }) {
  const [status, setStatus] = useState("PENDING");
  const [pdfUrl, setPdfUrl] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true, timer;
    const tick = async () => {
      try {
        const s = await api.getStatus(id);
        if (!alive) return;
        setStatus(s.status);
        if (s.status === "FAILED") setErr(s.error || "The research task failed.");
        else if (s.status === "COMPLETED") {
          if (MOCK) setSnapshot(await api.getSnapshot(ticker));
          else setPdfUrl(await api.getResult(id)); // one-shot: fetched exactly once
        } else timer = setTimeout(tick, 2500);
      } catch (x) { alive && setErr(x.message); }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [id, ticker]);

  if (err) return <p className="error" role="alert">Could not load this report: {err}</p>;

  if (status !== "COMPLETED") {
    return (
      <section className="hero">
        <h1>Working on {ticker}</h1>
        <ol className="stages live">
          {Object.entries(STAGE_INFO).filter(([k]) => k !== "COMPLETED").map(([key, s]) => (
            <li key={key} style={{ "--c": s.color }} className={status === key ? "active" : status === "COMPLETED" ? "done" : ""}>
              <b>{s.name}</b><span>{s.note}</span>
            </li>
          ))}
        </ol>
      </section>
    );
  }

  // Real mode: the backend only returns the finished PDF, so that's all we can show.
  if (!MOCK) {
    return (
      <section className="hero">
        <h1>{ticker} report is ready</h1>
        <p className="lede">This view is the PDF itself — the backend doesn't yet return the underlying ratios, sentiment or peer data separately, only the finished file.</p>
        <a className="cta" href={pdfUrl} download={`${ticker}.pdf`}>Download PDF</a>
        {pdfUrl && <iframe title={`${ticker} report`} src={pdfUrl} style={{ width: "100%", height: "80vh", border: "1px solid var(--glass-line)", borderRadius: 12, marginTop: "2rem" }} />}
      </section>
    );
  }

  // Mock mode: the richer memo layout, for demoing the intended design.
  const data = snapshot; const s = data.sentiment;
  function downloadDemoPdf() {
    const lines = [
      `${data.company} — Research Memo (demo data)`, "",
      data.summary, "",
      "Financial health:",
      ...data.ratios.map((r) => `  ${r.name}: ${r.value} (${r.status})`), "",
      `Sentiment: ${s.label} — ${s.positive}% positive, ${s.neutral}% neutral, ${s.negative}% negative`, "",
      `Against ${data.peer.ticker}:`,
      ...data.peer.rows.map((r) => `  ${r.metric} — ${data.company}: ${r.target}, ${data.peer.ticker}: ${r.peer}`),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([lines], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url; a.download = `${data.company}-demo-report.txt`; a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <article className="memo">
      <p className="meta">Research memo · demo data</p>
      <h1>{data.company}</h1>
      <p className="lede">{data.summary}</p>
      <button className="cta" onClick={downloadDemoPdf}>Download report</button>
      <p className="download-note">This is a plain-text stand-in — real PDFs come from your backend's /api/result once it's connected.</p>

      <h2>Financial health</h2>
      <table>
        <tbody>
          {data.ratios.map((r) => (
            <tr key={r.name}><td>{r.name}</td><td className="num">{r.value}</td><td><span className={`pill ${r.status}`}>{r.status}</span></td></tr>
          ))}
        </tbody>
      </table>

      <h2>News and transcript tone: {s.label}</h2>
      <div className="bar" role="img" aria-label={`${s.positive}% positive, ${s.neutral}% neutral, ${s.negative}% negative`}>
        <i className="p" style={{ width: s.positive + "%" }} />
        <i className="n" style={{ width: s.neutral + "%" }} />
        <i className="x" style={{ width: s.negative + "%" }} />
      </div>
      <p className="legend">{s.positive}% positive, {s.neutral}% neutral, {s.negative}% negative</p>

      <h2>Against {data.peer.ticker}</h2>
      <table>
        <thead><tr><th>Metric</th><th className="num">{data.company}</th><th className="num">{data.peer.ticker}</th></tr></thead>
        <tbody>
          {data.peer.rows.map((r) => (
            <tr key={r.metric}><td>{r.metric}</td><td className="num">{r.target}</td><td className="num">{r.peer}</td></tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}

export function History({ go }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.getHistory().then(setRows).catch(() => setRows([])); }, []);
  return (
    <section className="hero">
      <h1>Your past research</h1>
      {rows && rows.length === 0 && (
        <p className="lede">
          {MOCK ? "Nothing here yet. Run your first ticker from the home page."
                : "The backend doesn't have a history endpoint yet — searches are logged, but nothing reads them back."}
        </p>
      )}
      <ul className="history">
        {(rows || []).map((h) => (
          <li key={h.id}>
            <button onClick={() => go("report", { id: h.id, ticker: h.ticker })}>
              <b>{h.ticker}</b><span>{new Date(h.at).toLocaleString()}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Auth({ done }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    try { await api.auth(mode, f.email, f.password); done(); } catch (x) { setErr(x.message); }
  }
  return (
    <section className="auth-shell">
      <div className="auth-side narrow">
        <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <form onSubmit={submit} className="stack">
          <label>Email<input type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
          <label>Password<input type="password" required minLength={6} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
          {err && <p className="error" role="alert">{err}</p>}
          <button className="cta">{mode === "login" ? "Log in" : "Sign up"}</button>
        </form>
        <button className="link" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
          {mode === "login" ? "New here? Create an account" : "Have an account? Log in"}
        </button>
      </div>
      <div className="auth-visual">
        <p>Research that reads the filings so you don't have to.</p>
      </div>
    </section>
  );
}