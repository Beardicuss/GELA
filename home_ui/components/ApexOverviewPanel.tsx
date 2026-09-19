"use client";

import { useEffect, useState } from "react";

const ACCENT = "#dc5148";

export default function GelaOverviewPanel() {
  const [now, setNow] = useState<Date | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setNow(new Date());
    const timer = window.setInterval(() => setNow(new Date()), 30000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <div className="apex-overview" style={{ pointerEvents: "none" }}>
      <div style={{ position: "absolute", top: 14, left: 8, width: "min(520px, 94vw)", height: 220,
        background: `radial-gradient(ellipse 48% 70% at 46% 0%, ${ACCENT}${open ? "44" : "20"}, transparent 72%)`,
        filter: "blur(10px)", pointerEvents: "none" }} />
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}
        aria-label="Toggle Gela overview" style={{ position: "relative", height: 42, width: open ? 480 : 320,
          maxWidth: "90vw", cursor: "pointer", pointerEvents: "auto", background: "transparent", border: 0,
          color: ACCENT, textAlign: "left" }}>
        <span style={{ position: "absolute", top: 14, left: 8, right: 0, height: 2, background: ACCENT,
          boxShadow: `0 0 12px ${ACCENT}` }} />
        <span style={{ position: "absolute", top: 21, left: 10, fontSize: 9, letterSpacing: "0.34em",
          fontFamily: "var(--font-mono)" }}>GELA / OVERVIEW</span>
      </button>
      <div className="gela-overview-clock" style={{ pointerEvents: "auto" }}>
        <div style={{ fontSize: 34, fontWeight: 300, letterSpacing: "0.04em", color: "#f1e7e5", lineHeight: 1 }}>
          {now?.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }) || "--:--"}
        </div>
        <div style={{ fontSize: 11, letterSpacing: "0.18em", color: "#ad9a97", marginTop: 5, textTransform: "uppercase" }}>
          {now?.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) || ""}
        </div>
        {open && <div style={{ marginTop: 18, padding: "12px 15px", background: "#181111dd", border: `1px solid ${ACCENT}55`,
          color: "#d9bdb7", fontSize: 11, letterSpacing: "0.12em" }}>GELA HOME · LOCAL PC COMMAND CENTRE</div>}
      </div>
    </div>
  );
}
