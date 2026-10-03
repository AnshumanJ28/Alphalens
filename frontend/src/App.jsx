import { useEffect, useRef, useState } from "react";
import * as api from "./api";
import { Home, Report, History, Auth } from "./Pages";

/* Crisp, resolution-independent version of the neon chart look:
   floor grid + rising stems + glowing ribbon. Pure SVG, no image file needed. */
function ChartBackdrop() {
  const stems = Array.from({ length: 16 }, (_, i) => ({ x: 30 + i * 36, top: 140 + ((i * 137) % 360) }));
  const floorH = Array.from({ length: 9 }, (_, k) => 720 + 180 * Math.pow(k / 8, 2));
  const floorV = Array.from({ length: 13 }, (_, k) => -300 + k * 100);
  const ribbon = "-20,640 120,430 230,560 330,380 410,470 520,200 640,80";
  const line = { fill: "none", strokeLinecap: "round", strokeLinejoin: "round" };

  return (
    <svg className="chart-backdrop" viewBox="0 0 600 900" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="cb-ribbon" gradientUnits="userSpaceOnUse" x1="0" y1="640" x2="640" y2="80">
          <stop offset="0" stopColor="#7b3ff2" />
          <stop offset=".55" stopColor="#ff3fc9" />
          <stop offset="1" stopColor="#ffc2ee" />
        </linearGradient>
        <linearGradient id="cb-stem" gradientUnits="userSpaceOnUse" x1="0" y1="720" x2="0" y2="120">
          <stop offset="0" stopColor="#d9b8ff" stopOpacity=".45" />
          <stop offset="1" stopColor="#d9b8ff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="cb-floor" gradientUnits="userSpaceOnUse" x1="0" y1="720" x2="0" y2="900">
          <stop offset="0" stopColor="#c9a6e0" stopOpacity="0" />
          <stop offset=".4" stopColor="#c9a6e0" stopOpacity=".4" />
          <stop offset="1" stopColor="#c9a6e0" stopOpacity=".05" />
        </linearGradient>
        <radialGradient id="cb-halo" cx="55%" cy="40%" r="50%">
          <stop offset="0" stopColor="#ff3fc9" stopOpacity=".28" />
          <stop offset="1" stopColor="#ff3fc9" stopOpacity="0" />
        </radialGradient>
        <filter id="cb-blur-lg" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14" /></filter>
        <filter id="cb-blur-sm" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="4" /></filter>
      </defs>

      <rect width="600" height="900" fill="url(#cb-halo)" />

      {/* perspective floor */}
      {floorH.map((y) => <line key={y} x1="-300" x2="900" y1={y} y2={y} stroke="url(#cb-floor)" strokeWidth="1" />)}
      {floorV.map((x) => <line key={x} x1={300 + (x - 300) * 0.15} y1="720" x2={x} y2="900" stroke="url(#cb-floor)" strokeWidth="1" />)}

      {/* rising stems with glowing tips */}
      {stems.map((s) => (
        <g key={s.x}>
          <line x1={s.x} x2={s.x} y1="720" y2={s.top} stroke="url(#cb-stem)" strokeWidth="1" />
          <circle cx={s.x} cy={s.top} r="2.4" fill="#f3d9ff" opacity=".8" />
        </g>
      ))}

      {/* glowing ribbon: wide halo, body, bright core */}
      <polyline points={ribbon} {...line} stroke="url(#cb-ribbon)" strokeWidth="46" opacity=".5" filter="url(#cb-blur-lg)" />
      <polyline points={ribbon} {...line} stroke="url(#cb-ribbon)" strokeWidth="18" opacity=".55" filter="url(#cb-blur-sm)" />
      <polyline points={ribbon} {...line} stroke="#ffd6f3" strokeWidth="3" opacity=".85" />
    </svg>
  );
}

export default function App() {
  const [view, setView] = useState({ name: "home" });
  const [authed, setAuthed] = useState(false);
  const bgRef = useRef(null);

  useEffect(() => { api.isAuthed().then(setAuthed); }, []);
  const go = (name, params = {}) => setView({ name, ...params });

  // Parallax: background moves up at 0.5x of the scroll distance
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const y = Math.min(window.scrollY * 0.5, window.innerHeight * 0.6);
        bgRef.current?.style.setProperty("--parallax", `${-y}px`);
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <>
      <div className="bg-parallax" aria-hidden="true" ref={bgRef}>
        <div className="bg-parallax__move">
          <ChartBackdrop />
        </div>
      </div>

      <header className="nav">
        <button className="brand" onClick={() => go("home")}>
          <svg className="brand-mark" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
            <rect x="5.5" y="5.5" width="15" height="15" rx="2.5" transform="rotate(45 13 13)" fill="none" stroke="currentColor" strokeWidth="1.4" />
            <text x="13" y="17.5" textAnchor="middle" fontFamily="Bricolage Grotesque, sans-serif" fontWeight="700" fontSize="12" fill="currentColor">α</text>
          </svg>
          <span>Alphalens</span>
        </button>
        <nav>
          {authed && <button onClick={() => go("history")}>History</button>}
          {authed ? (
            <button onClick={() => api.logout().then(() => { setAuthed(false); go("home"); })}>Log out</button>
          ) : (
            <button onClick={() => go("login")}>Log in</button>
          )}
        </nav>
      </header>

      <main>
        {view.name === "home" && <Home go={go} authed={authed} />}
        {view.name === "login" && <Auth done={() => { setAuthed(true); go("home"); }} />}
        {view.name === "report" && <Report key={view.id} id={view.id} ticker={view.ticker} />}
        {view.name === "history" && <History go={go} />}
      </main>

      <footer className="footer">
        <div className="footer-top">
          <div className="footer-brand">
            <svg width="24" height="24" viewBox="0 0 26 26" aria-hidden="true">
              <rect x="5.5" y="5.5" width="15" height="15" rx="2.5" transform="rotate(45 13 13)" fill="none" stroke="currentColor" strokeWidth="1.4" />
              <text x="13" y="17.5" textAnchor="middle" fontFamily="Bricolage Grotesque, sans-serif" fontWeight="700" fontSize="12" fill="currentColor">α</text>
            </svg>
            <span>Alphalens</span>
            <p className="footer-tagline">The edge starts with the evidence.</p>
          </div>

          <div className="footer-col">
            <h3>Product</h3>
            <button onClick={() => go("home")}>Home</button>
            <button onClick={() => authed ? go("history") : go("login")}>History</button>
            <button onClick={() => go("login")}>{authed ? "Account" : "Log in"}</button>
          </div>

          <div className="footer-col">
            <h3>Project</h3>
            <a href="https://github.com/AnshumanJ28/invest-research-agent" target="_blank" rel="noreferrer">GitHub repo</a>
            <span className="footer-static">Capstone project, 2026</span>
          </div>

          <div className="footer-col">
            <h3>Connect</h3>
            <div className="footer-social">
              <a href="#" aria-label="GitHub" target="_blank" rel="noreferrer">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.73.5.5 5.73.5 12.02c0 5.05 3.29 9.33 7.86 10.84.57.1.78-.25.78-.55v-2.15c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.23-1.28-5.23-5.68 0-1.26.45-2.28 1.19-3.08-.12-.3-.52-1.5.11-3.12 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.62.23 2.82.11 3.12.74.8 1.19 1.82 1.19 3.08 0 4.41-2.69 5.38-5.25 5.67.41.36.78 1.07.78 2.15v3.19c0 .3.21.66.79.55A11.52 11.52 0 0 0 23.5 12c0-6.29-5.23-11.5-11.5-11.5Z"/></svg>
              </a>
              <a href="#" aria-label="LinkedIn" target="_blank" rel="noreferrer">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.86 0-2.14 1.45-2.14 2.95v5.66H9.34V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29ZM5.34 7.43a2.07 2.07 0 1 1 0-4.14 2.07 2.07 0 0 1 0 4.14ZM7.12 20.45H3.56V9h3.56v11.45Z"/></svg>
              </a>
              <a href="#" aria-label="X (Twitter)" target="_blank" rel="noreferrer">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M18.24 2.25h3.3l-7.2 8.23 8.47 11.27h-6.63l-5.19-6.8-5.94 6.8H1.76l7.7-8.8L1.36 2.25h6.8l4.69 6.2 5.39-6.2Zm-1.16 17.52h1.83L6.98 4.14H5.02l12.06 15.63Z"/></svg>
              </a>
              <a href="mailto:hello@alphalens.app" aria-label="Email">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="2.5" y="4.5" width="19" height="15" rx="2.2"/><path d="m3 6 9 7 9-7"/></svg>
              </a>
            </div>
          </div>
        </div>

        <p className="footer-note">Research generated by Alphalens is for informational purposes only and is not financial advice.</p>
        <div className="footer-bottom">
          <p>© {new Date().getFullYear()} Alphalens — built as a capstone project.</p>
          <p className="footer-stack">React · FastAPI · Celery · C++ · Java</p>
        </div>
      </footer>
    </>
  );
}