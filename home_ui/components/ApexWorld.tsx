"use client";

/**
 * Gela Home - adapted from the Apex visual experiment by Softcurse Systems.
 * Layers: dark backdrop → ReasoningWeb (agent constellation)
 * → 3D particle Gela avatar → OrbStatusBar.
 * Nodes open allowlisted Gela/Windows destinations. The core follows real status.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { OrbState } from "./ApexHeroOrb";
import ReasoningWebJs from "./ReasoningWeb";
import ShaderBackgroundJs from "./ShaderBackground";
import OrbStatusBar from "./OrbStatusBar";
import GelaCatalogPanel from "./GelaCatalogPanel";
import GelaDesktopPanel from "./GelaDesktopPanel";
import GelaControlPanel from "./GelaControlPanel";
import GelaShortcutsPanel from "./GelaShortcutsPanel";
import GelaHealthPanel, { type GelaHealth } from "./GelaHealthPanel";

const ApexHumanoidAvatar3D = dynamic(() => import("./ApexHumanoidAvatar3D"), { ssr: false });

export type NodeSel = { name: string; key: string; color: string };

// the copied .jsx defaults onSelect to null, which TS infers as `null | undefined`
const ReasoningWeb = ReasoningWebJs as unknown as React.ComponentType<{
  state?: string; trace?: unknown; mode?: string; coreless?: boolean;
  onSelect?: (n: NodeSel) => void; light?: boolean;
  roster?: unknown[]; maxFps?: number;
}>;
const ShaderBackground = ShaderBackgroundJs as unknown as React.ComponentType<{
  opacity?: number; voiceActive?: boolean; gold?: boolean; maxFps?: number;
}>;
type AgentInfo = {
  role: string;
  caps: string[];
  asks?: string[];
  status: "online" | "standby" | "integration";
};

/* Keep in sync with the graphical node roster in ReasoningWeb.jsx. */
export const ROSTER: { key: string; name: string; color: string }[] = [
  { key: "this_pc", name: "This PC", color: "#dc5148" },
  { key: "documents", name: "Documents", color: "#dc5148" },
  { key: "apps", name: "Apps", color: "#dc5148" },
  { key: "downloads", name: "Downloads", color: "#dc5148" },
  { key: "games", name: "Gaming Hub", color: "#dc5148" },
  { key: "music", name: "Media Library", color: "#dc5148" },
  { key: "search", name: "Windows Search", color: "#dc5148" },
  { key: "shortcuts", name: "Custom Circles", color: "#d99468" },
  { key: "settings", name: "Settings", color: "#d99468" },
  { key: "browsers", name: "Browsers", color: "#d99468" },
  { key: "task_manager", name: "Task Manager", color: "#d99468" },
  { key: "gela_control", name: "Gela Control", color: "#d99468" },
  { key: "recycle_bin", name: "Recycle Bin", color: "#d99468" },
  { key: "desktop", name: "Desktop Items", color: "#a4a0a0" },
];

const GRAPH_ROSTER: (string | number | boolean)[][] = [
  ["search", "Windows Search", "consultant", 296, 118, true, 18, 8], ["this_pc", "This PC", "consultant", 182, 150, true, 24, 8],
  ["documents", "Documents", "consultant", 250, 212, true, 18, 8], ["apps", "Apps", "consultant", 158, 266, true, 22, 8],
  ["downloads", "Downloads", "consultant", 195, 298, true, 20, 8], ["games", "Gaming Hub", "consultant", 232, 330, true, 20, 8],
  ["music", "Media Library", "consultant", 118, 356, true, 26, 8], ["desktop", "Desktop Items", "tool", 430, 118, true, -18, 8],
  ["browsers", "Browsers", "doer", 498, 150, true, -24, 8], ["task_manager", "Task Manager", "doer", 584, 208, true, -26, 8],
  ["settings", "Settings", "doer", 452, 250, true, -18, 8], ["recycle_bin", "Recycle Bin", "doer", 608, 286, true, -26, 8],
  ["shortcuts", "Custom Circles", "doer", 502, 312, true, -22, 8], ["gela_control", "Gela Control", "doer", 560, 356, true, -24, 8],
];
const SLOT_KEYS = ["", "search", "task_manager", "recycle_bin", "shortcuts"];
type PinnedCircle = { id: string; name: string; slot: number | null };

/* Honest descriptions of the destinations actually wired in this first slice. */
export const INFO: Record<string, AgentInfo> = {
  this_pc: { role: "Windows files and drives", status: "online", caps: ["Open This PC in File Explorer"] },
  documents: { role: "Your Documents folder", status: "online", caps: ["Open the Windows Documents folder"] },
  apps: { role: "Installed Windows applications", status: "online", caps: ["Browse and launch apps from Gela's catalog"] },
  downloads: { role: "Recent downloads", status: "online", caps: ["Open the Windows Downloads folder"] },
  games: { role: "Installed games library", status: "online", caps: ["Browse Steam games and standalone games you add"] },
  music: { role: "Gela media catalog", status: "online", caps: ["Browse allowlisted playlists, songs, videos, and images"] },
  search: { role: "Windows file and app search", status: "online", caps: ["Open Windows Search"] },
  shortcuts: { role: "Your configurable PC destinations", status: "online", caps: ["Add and name files, folders, programs, and drive roots", "Pin them directly to Circle 1–4"] },
  settings: { role: "Gela preferences", status: "online", caps: ["Open Gela Settings"] },
  browsers: { role: "Installed web browsers", status: "online", caps: ["Automatically list and launch browsers detected by Gela"] },
  task_manager: { role: "Windows process monitor", status: "online", caps: ["Open Task Manager"] },
  gela_control: { role: "Gela tools and configuration", status: "online", caps: ["Open Notes, Voice Names, Diagnostics, Logs, Routines, or Mobile Link"] },
  recycle_bin: { role: "Deleted Windows items", status: "online", caps: ["Open Recycle Bin"] },
  desktop: { role: "Desktop files and shortcuts", status: "online", caps: ["Browse the items currently on your Windows desktop"] },
};

const STATUS_LINE: Record<AgentInfo["status"], { color: string; text: string }> = {
  online: { color: "#d99468", text: "Ready to open" },
  standby: { color: "#c9a84c", text: "Standby - in active development" },
  integration: { color: "#7f9bb3", text: "Integration - wired into the core" },
};

/* ── AGENT OVERVIEW window - the site's template (the app opens live cockpits) ── */
export function AgentOverview({ sel, onClose, onLaunch }: { sel: NodeSel; onClose: () => void; onLaunch: (key: string) => void }) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef<{ sx: number; sy: number } | null>(null);
  const info = INFO[sel.key] ?? { role: "Destination", status: "online" as const, caps: ["Gela Home control"] };
  const c = sel.color;
  const status = STATUS_LINE[info.status];

  useEffect(() => {
    setPos({ x: Math.max(8, window.innerWidth / 2 - 170), y: Math.max(90, window.innerHeight * 0.16) });
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Move focus into the window when it opens and hand it back on close, so the
  // keyboard does not stay stranded on the agent list behind it.
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!pos) return;
    const opener = document.activeElement as HTMLElement | null;
    panelRef.current?.querySelector<HTMLElement>("button")?.focus();
    return () => { if (opener && document.contains(opener)) opener.focus(); };
  }, [pos]);

  const onMouseDown = (e: React.MouseEvent) => {
    if (!pos) return;
    dragRef.current = { sx: e.clientX - pos.x, sy: e.clientY - pos.y };
    const move = (ev: MouseEvent) => {
      if (dragRef.current) setPos({ x: ev.clientX - dragRef.current.sx, y: ev.clientY - dragRef.current.sy });
    };
    const up = () => {
      dragRef.current = null;
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  };

  if (!pos) return null;
  return (
    <div ref={panelRef} role="dialog" aria-modal="true" aria-label={`${sel.name} overview`} style={{
      position: "fixed", left: pos.x, top: pos.y,
      width: "min(340px, 92vw)", zIndex: 60,
      background: "rgba(4,3,12,0.92)",
      backdropFilter: "blur(24px)",
      border: `1px solid ${c}44`,
      borderRadius: 16,
      boxShadow: `0 0 40px ${c}18, 0 8px 32px rgba(0,0,0,0.6)`,
      overflow: "hidden",
    }}>
      {/* header - drag handle */}
      <div onMouseDown={onMouseDown} style={{
        display: "flex", alignItems: "center", gap: 10, padding: "14px 16px",
        borderBottom: `1px solid ${c}22`, cursor: "grab", userSelect: "none",
        background: `linear-gradient(135deg, ${c}0a 0%, transparent 100%)`,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: "50%", background: `${c}14`,
          border: `1px solid ${c}44`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: c, boxShadow: `0 0 10px ${c}` }} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "0.08em", color: c }}>{sel.name.toUpperCase()}</div>
          <div style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", letterSpacing: "0.06em", textTransform: "uppercase" }}>{info.role}</div>
        </div>
        <button onClick={onClose} aria-label="Close"
          style={{ marginLeft: "auto", background: "none", border: "none", color: "rgba(255,255,255,0.3)", cursor: "pointer", fontSize: 18, lineHeight: 1, padding: "6px 8px", transition: "color 0.2s" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.75)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "rgba(255,255,255,0.3)")}
        >×</button>
      </div>

      <div style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <div style={{ fontSize: 9, letterSpacing: "0.14em", color: `${c}99`, marginBottom: 8, fontFamily: "var(--font-mono)" }}>GELA DESTINATION</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {info.caps.map((cap) => (
              <div key={cap} style={{ display: "flex", alignItems: "flex-start", gap: 7 }}>
                <div style={{ width: 3, height: 3, borderRadius: "50%", background: `${c}99`, marginTop: 6, flexShrink: 0 }} />
                <span style={{ fontSize: 11.5, color: "rgba(255,255,255,0.6)", lineHeight: 1.55 }}>{cap}</span>
              </div>
            ))}
          </div>
        </div>

        {info.asks && info.asks.length > 0 && (
          <div>
            <div style={{ fontSize: 9, letterSpacing: "0.14em", color: `${c}99`, marginBottom: 8, fontFamily: "var(--font-mono)" }}>EXAMPLE REQUESTS</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {info.asks.map((task) => (
                <span key={task} style={{
                  padding: "4px 10px", background: `${c}0d`, border: `1px solid ${c}2a`,
                  borderRadius: 20, fontSize: 10.5, color: `${c}cc`,
                }}>{task}</span>
              ))}
            </div>
          </div>
        )}

        <button type="button" onClick={() => onLaunch(sel.key)} style={{
          padding: "11px 16px", background: "rgba(166, 37, 33, 0.24)", color: "#f3d0c8",
          border: "1px solid #b8443b", borderRadius: 5, cursor: "pointer", fontWeight: 700,
          letterSpacing: "0.12em", textTransform: "uppercase",
        }}>Open {sel.name} ↗</button>

        <div style={{ display: "flex", alignItems: "center", gap: 7, borderTop: `1px solid ${c}1a`, paddingTop: 12 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: status.color, boxShadow: `0 0 8px ${status.color}` }} />
          <span style={{ fontSize: 9.5, letterSpacing: "0.1em", color: "rgba(255,255,255,0.45)", textTransform: "uppercase" }}>{status.text}</span>
        </div>
      </div>
    </div>
  );
}

/* ── The world ── */
export default function ApexWorld() {
  const [selected, setSelected] = useState<NodeSel | null>(null);
  const [reduced, setReduced] = useState(false);
  const [gelaStatus, setGelaStatus] = useState("connecting");
  const [bridgeFresh, setBridgeFresh] = useState(false);
  const [workerFresh, setWorkerFresh] = useState(false);
  const [statusRecent, setStatusRecent] = useState(false);
  const [health, setHealth] = useState<GelaHealth | null>(null);
  const [healthOpen, setHealthOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [pinnedCircles, setPinnedCircles] = useState<PinnedCircle[]>([]);
  const [performanceMode, setPerformanceMode] = useState<"foreground" | "background" | "hidden">("foreground");
  useEffect(() => {
    const update = () => setPerformanceMode(document.hidden ? "hidden" : document.hasFocus() ? "foreground" : "background");
    update();
    window.addEventListener("focus", update);
    window.addEventListener("blur", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      window.removeEventListener("focus", update);
      window.removeEventListener("blur", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch("/api/gela", { cache: "no-store" });
        if (!response.ok) throw new Error("Health unavailable");
        const data = await response.json();
        if (active) {
          setGelaStatus(data.online ? String(data.status || "sleeping") : "offline");
          setBridgeFresh(Boolean(data.bridgeFresh));
          setWorkerFresh(Boolean(data.workerFresh));
          setStatusRecent(Boolean(data.statusRecent));
          setHealth(data);
        }
      } catch {
        if (active) { setGelaStatus("offline"); setBridgeFresh(false); setWorkerFresh(false); setStatusRecent(false); setHealth(null); }
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    let active = true;
    const refresh = () => fetch("/api/shortcuts?category=shortcut", { cache: "no-store" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data) => { if (active) setPinnedCircles((current) => {
        const next = data.items.filter((item: PinnedCircle) => item.slot);
        return JSON.stringify(current) === JSON.stringify(next) ? current : next;
      }); })
      .catch(() => { /* custom circles are optional */ });
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const pinnedByKey = useMemo(() => new Map(pinnedCircles.map((item) => [SLOT_KEYS[item.slot || 0], item])), [pinnedCircles]);
  const effectiveRoster = useMemo(() => ROSTER.map((item) => {
    const pinned = pinnedByKey.get(item.key);
    return pinned ? { ...item, key: `custom_${pinned.id}`, name: pinned.name } : item;
  }), [pinnedByKey]);
  const graphRoster = useMemo(() => GRAPH_ROSTER.map((row) => {
    const pinned = pinnedByKey.get(String(row[0]));
    return pinned ? [`custom_${pinned.id}`, pinned.name, ...row.slice(2)] : row;
  }), [pinnedByKey]);
  const orbState: OrbState = !workerFresh || !statusRecent ? "idle"
    : gelaStatus === "speaking" ? "speaking"
    : gelaStatus.startsWith("listening") || gelaStatus === "dictating" ? "listening"
    : gelaStatus === "executing" || gelaStatus === "answering_question" || gelaStatus === "transcribing_note" ? "thinking"
    : "idle";

  const launch = async (key: string) => {
    setFeedback("");
    try {
      const response = await fetch("/api/gela", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: key }),
      });
      const data = await response.json();
      setFeedback(response.ok ? `Opening ${ROSTER.find((item) => item.key === key)?.name ?? key}` : (data.error || "Could not open destination"));
      if (response.ok) setSelected(null);
    } catch {
      setFeedback("Gela Home could not reach its local control service.");
    }
  };

  // Single entry point for opening an agent, shared by the SVG graph and the
  // hidden accessible list, so both routes behave identically.
  const openAgent = (n: NodeSel) => {
    setHealthOpen(false);
    if (n.key.startsWith("custom_")) {
      const id = n.key.slice(7);
      fetch("/api/shortcuts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "launch", category: "shortcut", id }) })
        .then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.error); setFeedback(`Opening ${data.name}`); })
        .catch(() => setFeedback(`Could not open ${n.name}`));
      return;
    }
    setSelected(n);
  };

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  const webState = orbState === "thinking" ? "processing" : orbState === "speaking" ? "speaking" : orbState === "listening" ? "listening" : "standby";
  const renderFps = performanceMode === "hidden" ? 0 : performanceMode === "background" ? 2 : orbState === "idle" ? 24 : 50;

  return (
    <div className={`gela-world gela-performance-${performanceMode}`} data-render-fps={renderFps}
      style={{ position: "absolute", inset: 0, overflow: "hidden", userSelect: "none" }}>
      <div className="gela-hud-brand" aria-hidden="true"><span>◆</span> SOFTCURSE SYSTEMS // COMMAND NEXUS</div>
      {/* Windows Explorer remains the desktop. */}
      <button type="button" onClick={() => launch("desktop")} aria-label="Show normal Windows desktop" style={{
        position: "absolute", top: 22, right: 22, zIndex: 46,
        background: "rgba(19, 12, 13, 0.86)", border: "1px solid #80504b", borderRadius: 5,
        color: "#e8b5a9", padding: "8px 12px", cursor: "pointer", fontSize: 10,
        fontFamily: "var(--font-mono, monospace)", letterSpacing: "0.12em",
      }}>SHOW DESKTOP ↗</button>
      <button type="button" onClick={() => openAgent({ key: "shortcuts", name: "Custom Circles", color: "#d99468" })}
        aria-label="Add or edit custom circles" style={{
          position: "absolute", top: 62, right: 22, zIndex: 46, background: "rgba(19,12,13,.78)",
          border: "1px solid #65403b", borderRadius: 5, color: "#cf9286", padding: "7px 10px", cursor: "pointer",
          fontSize: 9, fontFamily: "var(--font-mono,monospace)", letterSpacing: ".11em",
        }}>CUSTOMIZE CIRCLES +</button>

      {/* Backdrop, waves, and warm glow behind the avatar. */}
      <div aria-hidden="true" style={{
        position: "absolute", inset: 0,
        background: "radial-gradient(ellipse 95% 88% at 50% 42%, #2c1717 0%, #1d1011 38%, #120d0e 72%, #0a0909 100%)",
      }} />
      <div className="gela-hud-grid" aria-hidden="true" />
      <div className="gela-scanlines" aria-hidden="true" />
      <div className="gela-corner gela-corner-tl" aria-hidden="true" />
      <div className="gela-corner gela-corner-br" aria-hidden="true" />

      {/* background waves - the app's WebGL shader at the app's opacity */}
      {!reduced && (
        <div aria-hidden="true" style={{ position: "absolute", inset: 0, zIndex: 0 }}>
          <ShaderBackground opacity={0.12} voiceActive={orbState === "speaking"} gold={false} maxFps={renderFps} />
        </div>
      )}

      {/* Warm light cast brightens while speaking. */}
      <div aria-hidden="true" style={{
        position: "absolute", inset: 0, zIndex: 1, pointerEvents: "none", mixBlendMode: "screen",
        background: `radial-gradient(circle at 50% 42%, rgba(205,54,50,${orbState === "speaking" ? 0.30 : 0.18}) 0%, rgba(166,37,33,0.08) 30%, rgba(12,9,9,0) 62%)`,
        transition: "background 0.6s ease",
      }} />

      {/* The reasoning web remains below the avatar. */}
      {/* The visual graph and hidden keyboard list share one action path. */}
      <div aria-hidden="true" style={{ position: "absolute", inset: 0, zIndex: 5 }}>
        <ReasoningWeb
          state={webState}
          mode="full"
          coreless
          roster={graphRoster}
          maxFps={renderFps}
          onSelect={(n: NodeSel) => { openAgent(n); }}
        />
      </div>

      {/* Keyboard and screen-reader equivalent of the agent graph. */}
      <nav className="visually-hidden" aria-label="Gela Home destinations">
        <ul>
          {effectiveRoster.map((a) => (
            <li key={a.key}>
              <button type="button" onClick={() => openAgent({ key: a.key, name: a.name, color: a.color })}>
                {a.name} - {INFO[a.key]?.role ?? "Destination"}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* The avatar floats above the web but never intercepts node clicks. */}
      <div style={{ position: "absolute", inset: 0, zIndex: 6, pointerEvents: "none" }}>
        <div className="gela-holo-ring gela-holo-ring-a" aria-hidden="true" />
        <div className="gela-holo-ring gela-holo-ring-b" aria-hidden="true" />
        <div aria-hidden="true" style={{
          position: "absolute", left: "50%", top: "50%", transform: "translate(-50%, -50%)",
          width: "min(440px, 45vw)", height: "min(660px, 74vh)",
          background: "radial-gradient(ellipse at center, rgba(29,16,17,0.93) 0%, rgba(29,16,17,0.81) 38%, rgba(29,16,17,0) 72%)",
        }} />
        <ApexHumanoidAvatar3D state={orbState} interactive={false} maxFps={renderFps} />
      </div>

      {/* equalizer + STANDBY cluster */}
      <OrbStatusBar state={orbState} statusText={workerFresh ? gelaStatus : "unverified"} />
      <button type="button" onClick={() => { setSelected(null); setHealthOpen((open) => !open); }} aria-expanded={healthOpen}
        aria-label="Open Gela system health" style={{ position: "absolute", bottom: 15, left: 24, zIndex: 30,
          color: "#d99468", fontSize: 11, letterSpacing: "0.1em", background: "transparent",
          border: 0, borderBottom: "1px solid #744138", cursor: "pointer", textAlign: "left", padding: "2px 0",
          maxWidth: "calc(100vw - 48px)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {feedback || `GELA / WORKER ${workerFresh ? "LIVE" : "UNVERIFIED"} · PC LINK ${bridgeFresh ? "LIVE" : "UNVERIFIED"}`}
        <span style={{ color: "#8f6c66", marginLeft: 8 }}>▴ HEALTH</span>
      </button>
      {healthOpen && <GelaHealthPanel health={health} onClose={() => setHealthOpen(false)} />}
      {selected && (selected.key === "desktop"
        ? <GelaDesktopPanel onClose={() => setSelected(null)} />
        : selected.key === "gela_control"
        ? <GelaControlPanel onClose={() => setSelected(null)} onLaunch={launch} />
        : selected.key === "shortcuts"
        ? <GelaShortcutsPanel onClose={() => setSelected(null)} onFeedback={setFeedback} />
        : selected.key === "apps" || selected.key === "games" || selected.key === "music" || selected.key === "browsers"
        ? <GelaCatalogPanel kind={selected.key === "music" ? "media" : selected.key}
            onClose={() => setSelected(null)} onFeedback={setFeedback} />
        : <AgentOverview sel={selected} onClose={() => setSelected(null)} onLaunch={launch} />)}
    </div>
  );
}
