import { useEffect, useState } from "react";
import * as api from "./api";

/* ── Loading animation: 3 stock bars ─────────────────────────────────── */
function StockBarsLoader({ ticker }) {
  return (
    <section className="hero loading-section">
      <h1 className="loading-title">Analyzing {ticker}</h1>
      <p className="lede">Gathering financial data, crunching ratios, scoring sentiment…</p>
      <div className="stock-bars-loader">
        <div className="stock-bar" style={{ "--i": 0 }} />
        <div className="stock-bar" style={{ "--i": 1 }} />
        <div className="stock-bar" style={{ "--i": 2 }} />
      </div>
    </section>
  );
}

/* ── Metric card for the report view ────────────────────────────────── */
function MetricCard({ label, value, status, icon }) {
  return (
    <div className={`metric-card ${status || ""}`}>
      <div className="metric-icon">{icon}</div>
      <div className="metric-body">
        <span className="metric-label">{label}</span>
        <span className="metric-value">{value}</span>
      </div>
      {status && <span className={`pill ${status}`}>{status}</span>}
    </div>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────── */
function healthFlag(name, val) {
  if (name === "pe_ratio") return val < 20 ? "healthy" : val < 35 ? "watch" : "concerning";
  if (name === "current_ratio") return val > 1.5 ? "healthy" : val > 1.0 ? "watch" : "concerning";
  if (name === "net_margin") return val > 0.12 ? "healthy" : val > 0.05 ? "watch" : "concerning";
  if (name === "debt_to_equity") return val < 0.5 ? "healthy" : val < 1.0 ? "watch" : "concerning";
  return "watch";
}

function formatRatio(name, val) {
  if (name.includes("margin") || name === "roe" || name === "roa") return (val * 100).toFixed(2) + "%";
  return val?.toFixed(2) ?? "—";
}

export function Home({ go, authed }) {
  const [ticker, setTicker] = useState("");
  const [err, setErr] = useState("");

  async function submit(e) {
    e.preventDefault();
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
        <button className="cta">Run research</button>
      </form>
      {err && <p className="error" role="alert">{err}</p>}
    </section>
  );
}

export function Report({ id, ticker }) {
  const [status, setStatus] = useState("PENDING");
  const [snapshot, setSnapshot] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
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
          // Fetch JSON snapshot for metrics display
          try {
            const data = await api.getResultJSON(id);
            if (alive) setSnapshot(data);
          } catch { /* JSON endpoint might not exist, fall through */ }
          // Fetch PDF for download
          try {
            const url = await api.getResult(id);
            if (alive) setPdfUrl(url);
          } catch { /* PDF might not exist */ }
        } else timer = setTimeout(tick, 2500);
      } catch (x) { alive && setErr(x.message); }
    };
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [id, ticker]);

  if (err) return <p className="error" role="alert">Could not load this report: {err}</p>;

  if (status !== "COMPLETED") {
    return <StockBarsLoader ticker={ticker} />;
  }

  // --- Pick 5 key metrics from the snapshot ---
  const metrics = [];
  if (snapshot) {
    // Composite score
    metrics.push({
      label: "Composite Score",
      value: snapshot.composite_score != null ? `${snapshot.composite_score.toFixed(1)} / 10` : "—",
      status: snapshot.composite_score >= 7 ? "healthy" : snapshot.composite_score >= 5 ? "watch" : "concerning",
    });

    // Conviction
    metrics.push({
      label: "Conviction",
      value: snapshot.conviction_label || "—",
      status: (snapshot.conviction_label || "").includes("BUY") ? "healthy" : "watch",
    });

    // Sentiment
    const sentLabel = snapshot.sentiment?.overall_label || "—";
    const sentScore = snapshot.sentiment?.overall_score;
    metrics.push({
      label: "Sentiment",
      value: sentLabel + (sentScore != null ? ` (${sentScore.toFixed(2)})` : ""),
      status: sentScore > 0.05 ? "healthy" : sentScore < -0.05 ? "concerning" : "watch",
    });

    // Pick 2 key ratios from the ratios array
    const ratioMap = {};
    (snapshot.ratios || []).forEach((r) => { ratioMap[r.name] = r; });

    const peRatio = ratioMap["pe_ratio"];
    if (peRatio && peRatio.value != null) {
      metrics.push({
        label: "P/E Ratio",
        value: peRatio.formatted || peRatio.value.toFixed(2),
        status: peRatio.health_flag?.toLowerCase() || healthFlag("pe_ratio", peRatio.value),
      });
    }

    const netMargin = ratioMap["net_margin"];
    if (netMargin && netMargin.value != null) {
      metrics.push({
        label: "Net Margin",
        value: netMargin.formatted || formatRatio("net_margin", netMargin.value),
        status: netMargin.health_flag?.toLowerCase() || healthFlag("net_margin", netMargin.value),
      });
    }
  }

  return (
    <article className="report-view">
      <p className="meta">Research Report</p>
      <h1>{ticker.replace(".NS", "")} <span className="ticker-suffix">{ticker.includes(".") ? ticker.slice(ticker.indexOf(".")) : ""}</span></h1>

      {metrics.length > 0 && (
        <div className="minimal-metrics-wrapper">
          <table className="metrics-table">
            <tbody>
              {metrics.map((m, i) => (
                <tr key={i}>
                  <th>{m.label}</th>
                  <td className="metric-val">{m.value}</td>
                  <td className="metric-status">
                    {m.status && <span className={`pill ${m.status}`}>{m.status}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pdfUrl && (
        <div className="pdf-download-section">
          <p className="pdf-note">For a more detailed breakdown, download the full PDF report.</p>
          <a className="cta" href={pdfUrl} download={`${ticker}.pdf`}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: 8 }}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Download PDF
          </a>
        </div>
      )}

      {!snapshot && !pdfUrl && (
        <p className="lede">Report data is loading…</p>
      )}
    </article>
  );
}

/* ── Kept for future use ─────────────────────────────────────────────── */

// Old stage info for reference
// const STAGE_INFO = {
//   PENDING: { name: "Queued", note: "Waiting for a worker", color: "var(--mute)" },
//   PROCESSING: { name: "Researching", note: "Gathering data and crunching numbers", color: "var(--lilac)" },
//   COMPLETED: { name: "Done", note: "Your report is ready", color: "var(--chrome-done)" },
// };

export function History({ go }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.getHistory().then(setRows).catch(() => setRows([])); }, []);
  return (
    <section className="hero">
      <h1>Your past research</h1>
      {rows && rows.length === 0 && (
        <p className="lede">Nothing here yet. Run your first ticker from the home page.</p>
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