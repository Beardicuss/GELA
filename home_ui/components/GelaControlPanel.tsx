"use client";

import { useEffect } from "react";

const TOOLS = [
  ["notes", "Gela Notes", "Dictation notebook"],
  ["voice_names", "Voice Names", "Georgian and English app aliases"],
  ["routines", "Routines", "Multi-app command sequences"],
  ["mobile", "Mobile Link", "Phone pairing and remote control"],
  ["diagnostics", "Diagnostics", "Live Gela status and troubleshooting"],
  ["logs", "Logs", "Gela event history"],
] as const;

export default function GelaControlPanel({ onClose, onLaunch }: { onClose: () => void; onLaunch: (key: string) => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return <div role="dialog" aria-modal="true" aria-label="Gela Control" style={{
    position: "fixed", top: "12vh", left: "50%", transform: "translateX(-50%)", zIndex: 70,
    width: "min(620px, calc(100vw - 32px))", background: "rgba(17,12,13,.97)", color: "#f0e8e6",
    border: "1px solid #a63d37", borderRadius: 10, boxShadow: "0 20px 70px #000b,0 0 42px #942a2928", overflow: "hidden",
  }}>
    <div style={{ display: "flex", padding: "18px 20px", alignItems: "center", borderBottom: "1px solid #69302e" }}>
      <div style={{ flex: 1 }}><div style={{ color: "#ef8175", fontSize: 11, fontWeight: 700, letterSpacing: ".2em" }}>GELA / CONTROL</div>
        <div style={{ color: "#a99491", fontSize: 11, marginTop: 4 }}>Gela-specific tools are grouped here to keep Home focused on your PC.</div></div>
      <button onClick={onClose} aria-label="Close Gela Control" style={{ background: "transparent", border: 0, color: "#d9b4ae", fontSize: 22, cursor: "pointer" }}>×</button>
    </div>
    <div style={{ padding: 20, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      {TOOLS.map(([key, name, detail]) => <button key={key} onClick={() => onLaunch(key)} style={{
        textAlign: "left", padding: "15px 16px", background: "#1f1314", border: "1px solid #68312e", borderRadius: 6,
        color: "#f0e8e6", cursor: "pointer",
      }}><span style={{ display: "block", color: "#ef8175", fontSize: 12, fontWeight: 700, letterSpacing: ".1em" }}>{name.toUpperCase()} ↗</span>
        <span style={{ display: "block", color: "#aa9490", fontSize: 11, marginTop: 6 }}>{detail}</span></button>)}
    </div>
  </div>;
}
