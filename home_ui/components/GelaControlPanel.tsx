"use client";

import { useEffect, useState } from "react";
import GelaAvatarManager from "./GelaAvatarManager";

const TOOLS = [
  ["notes", "Gela Notes", "Dictation notebook"],
  ["voice_names", "Voice Names", "Georgian and English app aliases"],
  ["routines", "Routines", "Multi-app command sequences"],
  ["mobile", "Mobile Link", "Phone pairing and remote control"],
  ["diagnostics", "Diagnostics", "Live Gela status and troubleshooting"],
  ["logs", "Logs", "Gela event history"],
  ["avatar", "Avatar Manager", "Choose and preview a GLB hologram"],
] as const;

export default function GelaControlPanel({ onClose, onLaunch }: { onClose: () => void; onLaunch: (key: string) => void }) {
  const [avatarOpen, setAvatarOpen] = useState(false);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return <div role="dialog" aria-modal="true" aria-label="Gela Control" style={{
    position: "fixed", top: "12vh", left: "50%", transform: "translateX(-50%)", zIndex: 70,
    width: "min(620px, calc(100vw - 32px))", background: "rgba(5,8,16,.97)", color: "#e8f4f8",
    border: "1px solid rgba(0,255,255,.4)", borderRadius: 10, boxShadow: "0 20px 70px #000b,0 0 42px rgba(0,255,255,.1)", overflow: "hidden",
  }}>
    <div style={{ display: "flex", padding: "18px 20px", alignItems: "center", borderBottom: "1px solid rgba(0,255,255,.2)" }}>
      <div style={{ flex: 1 }}><div style={{ color: "#00ffff", fontSize: 11, fontWeight: 700, letterSpacing: ".2em" }}>GELA / CONTROL</div>
        <div style={{ color: "rgba(232,244,248,.62)", fontSize: 11, marginTop: 4 }}>Gela-specific tools are grouped here to keep Home focused on your PC.</div></div>
      <button onClick={onClose} aria-label="Close Gela Control" style={{ background: "transparent", border: 0, color: "#d9b4ae", fontSize: 22, cursor: "pointer" }}>×</button>
    </div>
    {avatarOpen ? <GelaAvatarManager onClose={() => setAvatarOpen(false)} /> : <div style={{ padding: 20, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
      {TOOLS.map(([key, name, detail]) => <button key={key} onClick={() => key === "avatar" ? setAvatarOpen(true) : onLaunch(key)} style={{
        textAlign: "left", padding: "15px 16px", background: "rgba(0,255,255,.045)", border: "1px solid rgba(0,255,255,.2)", borderRadius: 6,
        color: "#e8f4f8", cursor: "pointer",
      }}><span style={{ display: "block", color: "#00ffff", fontSize: 12, fontWeight: 700, letterSpacing: ".1em" }}>{name.toUpperCase()} ↗</span>
        <span style={{ display: "block", color: "#aa9490", fontSize: 11, marginTop: 6 }}>{detail}</span></button>)}
    </div>}
  </div>;
}
