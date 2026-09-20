"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type DesktopItem = { name: string; source: "Personal" | "Public"; type: "file" | "folder" | "shortcut" };

export default function GelaDesktopPanel({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<DesktopItem[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/desktop", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Desktop unavailable");
        setItems(data.items);
      })
      .catch((failure) => { if (!controller.signal.aborted) setError(String(failure.message || failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    searchRef.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return needle ? items.filter((item) => item.name.toLocaleLowerCase().includes(needle)) : items;
  }, [items, query]);

  return <div role="dialog" aria-modal="true" aria-label="Desktop Items" style={{
    position: "fixed", top: "11vh", left: "50%", transform: "translateX(-50%)",
    width: "min(560px, calc(100vw - 32px))", maxHeight: "78vh", zIndex: 70,
    display: "flex", flexDirection: "column", background: "rgba(5,8,16,.97)",
    border: "1px solid rgba(0,255,255,.4)", borderRadius: 10, boxShadow: "0 20px 70px #000b,0 0 42px rgba(0,255,255,.1)",
    color: "#e8f4f8", overflow: "hidden",
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "18px 20px", borderBottom: "1px solid rgba(0,255,255,.2)" }}>
      <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#00ffff", boxShadow: "0 0 12px #00ffff" }} />
      <div style={{ flex: 1 }}>
        <div style={{ color: "#00ffff", fontSize: 11, fontWeight: 700, letterSpacing: "0.2em" }}>GELA / DESKTOP ITEMS</div>
        <div style={{ color: "rgba(232,244,248,.62)", fontSize: 11, marginTop: 3 }}>
          {loading ? "Reading Windows Desktop…" : `${filtered.length} of ${items.length} items · personal and public desktop`}
        </div>
      </div>
      <button type="button" onClick={onClose} aria-label="Close desktop items" style={{ background: "transparent", border: 0,
        color: "#d9b4ae", cursor: "pointer", fontSize: 22, padding: "2px 8px" }}>×</button>
    </div>
    <div style={{ padding: "14px 20px 10px" }}>
      <input ref={searchRef} type="search" value={query} onChange={(event) => setQuery(event.target.value)}
        placeholder="Search desktop files and shortcuts…" aria-label="Search desktop items"
        style={{ width: "100%", background: "#020710", color: "#e8f4f8", border: "1px solid rgba(0,255,255,.28)",
          borderRadius: 5, outlineColor: "#00ffff", padding: "11px 13px", fontSize: 14 }} />
      <div style={{ color: "#a99491", fontSize: 11, marginTop: 10 }}>This is a live, read-only list. Use SHOW DESKTOP to switch to Windows.</div>
    </div>
    {error && <div role="alert" style={{ color: "#f3a79e", padding: "5px 20px 12px", fontSize: 12 }}>{error}</div>}
    <div style={{ overflowY: "auto", padding: "4px 20px 20px", minHeight: 100 }}>
      {!loading && filtered.length === 0 && !error && <div style={{ padding: 16, color: "#ad9692", fontSize: 13 }}>No matching items.</div>}
      {filtered.map((item, index) => <div key={`${item.source}-${item.name}-${index}`} style={{ display: "flex", alignItems: "center", gap: 12,
        borderBottom: "1px solid #4e2927", padding: "10px 0" }}>
        <span aria-hidden="true" style={{ color: "#00ffff", fontSize: 14, width: 18 }}>{item.type === "folder" ? "▣" : item.type === "shortcut" ? "↗" : "▤"}</span>
        <span style={{ flex: 1, fontSize: 13, overflowWrap: "anywhere" }}>{item.name}</span>
        <span style={{ color: "#a99491", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>{item.source} {item.type}</span>
      </div>)}
    </div>
  </div>;
}
