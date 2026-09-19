"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Kind = "apps" | "games" | "media" | "browsers";
type Item = { id: string; name: string; custom?: boolean };

export default function GelaCatalogPanel({ kind, onClose, onFeedback }: {
  kind: Kind;
  onClose: () => void;
  onFeedback: (message: string) => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const title = kind === "apps" ? "APPLICATIONS" : kind === "games" ? "GAMING HUB" : kind === "browsers" ? "BROWSERS" : "MEDIA LIBRARY";

  const load = async (signal?: AbortSignal) => {
    const response = await fetch(`/api/catalog?kind=${kind}`, { cache: "no-store", signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Catalog unavailable");
    let next: Item[] = data.items;
    if (kind === "games") {
      const customResponse = await fetch("/api/shortcuts?category=game", { cache: "no-store", signal });
      const customData = await customResponse.json();
      if (customResponse.ok) next = [...next, ...customData.items.map((item: Item) => ({ ...item, custom: true }))]
        .sort((a, b) => a.name.localeCompare(b.name));
    }
    setItems(next);
    setError("");
  };

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    load(controller.signal)
      .catch((failure) => { if (!controller.signal.aborted) setError(String(failure.message || failure)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [kind]);

  useEffect(() => {
    searchRef.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape" && !busy) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return needle ? items.filter((item) => item.name.toLocaleLowerCase().includes(needle)) : items;
  }, [items, query]);

  const launch = async (item: Item) => {
    setBusy(item.id);
    setError("");
    try {
      const response = await fetch(item.custom ? "/api/shortcuts" : "/api/catalog", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item.custom ? { action: "launch", category: "game", id: item.id } : { kind, id: item.id }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Launch failed");
      onFeedback(`Gela confirmed: ${item.name}`);
      onClose();
    } catch (failure) {
      setError(String(failure instanceof Error ? failure.message : failure));
    } finally {
      setBusy(null);
    }
  };

  const addGame = async () => {
    setBusy("picker"); setError("");
    try {
      const response = await fetch("/api/shortcuts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pick_file", category: "game" }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not add game");
      if (!data.cancelled) await load();
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); }
    finally { setBusy(null); }
  };

  const removeGame = async (item: Item) => {
    setBusy(item.id); setError("");
    try {
      const response = await fetch("/api/shortcuts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "remove", category: "game", id: item.id }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not remove game");
      await load();
    } catch (failure) { setError(String(failure instanceof Error ? failure.message : failure)); }
    finally { setBusy(null); }
  };

  return (
    <div role="dialog" aria-modal="true" aria-label={title} style={{
      position: "fixed", top: "11vh", left: "50%", transform: "translateX(-50%)",
      width: "min(560px, calc(100vw - 32px))", maxHeight: "78vh", zIndex: 70,
      display: "flex", flexDirection: "column", background: "rgba(17, 12, 13, 0.97)",
      border: "1px solid #a63d37", borderRadius: 10, boxShadow: "0 20px 70px #000b, 0 0 42px #942a2928",
      color: "#f0e8e6", overflow: "hidden",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "18px 20px", borderBottom: "1px solid #69302e" }}>
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#dc5148", boxShadow: "0 0 12px #dc5148" }} />
        <div style={{ flex: 1 }}>
          <div style={{ color: "#ef8175", fontSize: 11, fontWeight: 700, letterSpacing: "0.2em" }}>GELA / {title}</div>
          <div style={{ color: "#a99491", fontSize: 11, marginTop: 3 }}>
            {loading ? "Reading Gela's catalog…" : `${filtered.length} of ${items.length} available`}
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Close catalog" style={{ background: "transparent", border: 0,
          color: "#d9b4ae", cursor: "pointer", fontSize: 22, padding: "2px 8px" }}>×</button>
      </div>
      <div style={{ padding: "14px 20px 10px" }}>
        {kind === "games" && <button type="button" disabled={busy !== null} onClick={addGame} style={{
          marginBottom: 10, background: "#341c1b", color: "#e9a69c", border: "1px solid #93443e", borderRadius: 4,
          padding: "8px 11px", cursor: busy ? "wait" : "pointer", fontSize: 10, fontWeight: 700, letterSpacing: ".12em",
        }}>+ ADD STANDALONE GAME</button>}
        <input ref={searchRef} type="search" value={query} onChange={(event) => setQuery(event.target.value)}
          placeholder={`Search ${title.toLowerCase()}…`} aria-label={`Search ${title.toLowerCase()}`}
          style={{ width: "100%", background: "#0c090a", color: "#f0e8e6", border: "1px solid #70403b",
            borderRadius: 5, outlineColor: "#dc5148", padding: "11px 13px", fontSize: 14 }} />
      </div>
      {error && <div role="alert" style={{ color: "#f3a79e", padding: "5px 20px 12px", fontSize: 12 }}>{error}</div>}
      <div style={{ overflowY: "auto", padding: "4px 20px 20px", minHeight: 100 }}>
        {!loading && filtered.length === 0 && !error && <div style={{ padding: 16, color: "#ad9692", fontSize: 13 }}>No matching items.</div>}
        {filtered.slice(0, 100).map((item) => (
          <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 12,
            borderBottom: "1px solid #4e2927", padding: "8px 0" }}>
            <span style={{ flex: 1, fontSize: 13, overflowWrap: "anywhere" }}>{item.name}</span>
            <button type="button" disabled={busy !== null} onClick={() => launch(item)}
              style={{ background: busy === item.id ? "#512b29" : "#341c1b", color: "#e9a69c",
                border: "1px solid #93443e", borderRadius: 4, padding: "7px 11px", cursor: busy ? "wait" : "pointer",
                fontSize: 10, fontWeight: 700, letterSpacing: "0.13em" }}>
              {busy === item.id ? "CHECKING…" : "LAUNCH ↗"}
            </button>
            {item.custom && <button type="button" disabled={busy !== null} onClick={() => removeGame(item)}
              aria-label={`Remove ${item.name} from Gaming Hub`} style={{ background: "transparent", color: "#ad8882",
                border: "1px solid #633431", borderRadius: 4, padding: "7px 9px", cursor: busy ? "wait" : "pointer", fontSize: 10 }}>REMOVE</button>}
          </div>
        ))}
        {filtered.length > 100 && <div style={{ color: "#9b8581", fontSize: 11, paddingTop: 12 }}>Showing the first 100. Search to narrow the list.</div>}
      </div>
    </div>
  );
}
