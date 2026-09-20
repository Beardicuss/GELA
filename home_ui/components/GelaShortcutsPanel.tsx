"use client";

import { useCallback, useEffect, useState } from "react";

type Item = { id: string; name: string; type: string; slot: number | null };

export default function GelaShortcutsPanel({ onClose, onFeedback }: { onClose: () => void; onFeedback: (value: string) => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const response = await fetch("/api/shortcuts?category=shortcut", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Shortcuts unavailable");
    setItems(data.items);
  }, []);
  useEffect(() => { load().catch((failure) => setError(String(failure.message || failure))); }, [load]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);
  const act = async (action: string, id?: string, extra: Record<string, unknown> = {}) => {
    setBusy(true); setError("");
    try {
      const response = await fetch("/api/shortcuts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, category: "shortcut", id, ...extra }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Action failed");
      if (!data.cancelled) await load();
      if (action === "launch") onFeedback(`Opening ${data.name}`);
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); }
    finally { setBusy(false); }
  };
  return <div role="dialog" aria-modal="true" aria-label="Custom Circles" style={{
    position: "fixed", top: "10vh", left: "50%", transform: "translateX(-50%)", zIndex: 70,
    width: "min(640px,calc(100vw - 32px))", maxHeight: "80vh", display: "flex", flexDirection: "column",
    background: "rgba(5,8,16,.97)", color: "#e8f4f8", border: "1px solid rgba(0,255,255,.4)", borderRadius: 10, boxShadow: "0 20px 70px #000b,0 0 42px rgba(0,255,255,.1)", overflow: "hidden",
  }}>
    <div style={{ display: "flex", alignItems: "center", padding: "18px 20px", borderBottom: "1px solid rgba(0,255,255,.2)" }}>
      <div style={{ flex: 1 }}><div style={{ color: "#00ffff", fontSize: 11, fontWeight: 700, letterSpacing: ".2em" }}>GELA / CUSTOM CIRCLES</div>
        <div style={{ color: "rgba(232,244,248,.62)", fontSize: 11, marginTop: 4 }}>1. Add a target · 2. Type its circle name · 3. Assign Circle 1–4.</div></div>
      <button onClick={onClose} aria-label="Close shortcuts" style={{ background: "transparent", border: 0, color: "#d9b4ae", fontSize: 22, cursor: "pointer" }}>×</button>
    </div>
    <div style={{ display: "flex", gap: 8, padding: "12px 20px", borderBottom: "1px solid #4e2927" }}>
      <button disabled={busy} onClick={() => act("pick_file")} style={buttonStyle}>+ FILE / PROGRAM</button>
      <button disabled={busy} onClick={() => act("pick_folder")} style={buttonStyle}>+ FOLDER / DRIVE</button>
    </div>
    {error && <div role="alert" style={{ color: "#f3a79e", padding: "10px 20px" }}>{error}</div>}
    <div style={{ padding: "4px 20px 20px", overflowY: "auto" }}>
      {!items.length && !error && <div style={{ color: "#a99491", padding: 20 }}>No custom shortcuts yet.</div>}
      {items.map((item) => <div key={item.id} style={{ display: "flex", gap: 10, alignItems: "center", padding: "10px 0", borderBottom: "1px solid #4e2927" }}>
        <span style={{ color: "#ff9500" }}>{item.type === "folder" || item.type === "drive" ? "▣" : "↗"}</span>
        <input defaultValue={item.name} aria-label={`Circle name for ${item.name}`}
          onBlur={(event) => { const name = event.currentTarget.value.trim(); if (name && name !== item.name) void act("rename", item.id, { name }); }}
          style={{ flex: 1, minWidth: 100, background: "#020710", color: "#e8f4f8", border: "1px solid rgba(0,255,255,.22)", borderRadius: 4, padding: "7px 8px" }} />
        <span style={{ color: "#927d79", fontSize: 10, textTransform: "uppercase" }}>{item.type}</span>
        <select value={item.slot || 0} aria-label={`Circle slot for ${item.name}`}
          onChange={(event) => void act("pin", item.id, { slot: Number(event.currentTarget.value) })}
          style={{ background: "#1c1213", color: "#d9b4ae", border: "1px solid #633431", borderRadius: 4, padding: "7px" }}>
          <option value={0}>LIST ONLY</option><option value={1}>CIRCLE 1</option><option value={2}>CIRCLE 2</option>
          <option value={3}>CIRCLE 3</option><option value={4}>CIRCLE 4</option>
        </select>
        <button disabled={busy} onClick={() => act("launch", item.id)} style={buttonStyle}>OPEN</button>
        <button disabled={busy} onClick={() => act("remove", item.id)} style={{ ...buttonStyle, color: "#b58c86" }}>REMOVE</button>
      </div>)}
    </div>
  </div>;
}

const buttonStyle = { background: "rgba(0,255,255,.06)", color: "#00ffff", border: "1px solid rgba(0,255,255,.3)", borderRadius: 4,
  padding: "8px 11px", cursor: "pointer", fontSize: 10, fontWeight: 700, letterSpacing: ".08em" } as const;
