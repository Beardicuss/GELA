"use client";

import { useEffect, useRef } from "react";

export type GelaHealth = {
  online: boolean;
  status: string;
  updatedAt?: string;
  bridgeFresh: boolean;
  workerFresh: boolean;
  statusRecent: boolean;
  supervisorState: string;
  supervisorUpdatedAt?: string | null;
  microphone?: string;
  microphoneState?: string;
  models?: string;
  catalog?: string;
  lastExecution?: string;
};

function timeLabel(value?: string | null): string {
  if (!value) return "unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "unknown" : date.toLocaleString();
}

export default function GelaHealthPanel({ health, onClose }: {
  health: GelaHealth | null;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const rows = [
    ["PC link", health?.bridgeFresh ? "Live bridge heartbeat" : "Not verified"],
    ["Gela worker", health?.workerFresh ? "Live worker heartbeat" : "No recent heartbeat (older installs have none)"],
    ["Last state", health?.online ? `${health.status} · ${health.statusRecent ? "recent" : "last reported"} ${timeLabel(health.updatedAt)}` : "No status snapshot"],
    ["Supervisor", health?.supervisorState === "running" ? "Running (last report)" : health?.supervisorState || "Unknown"],
    ["Microphone", health?.microphoneState || "Unknown"],
    ["Models", health?.models || "Unknown"],
    ["Catalog", health?.catalog || "Unknown"],
    ["Last action", health?.lastExecution || "None yet"],
  ];

  return (
    <div role="dialog" aria-modal="true" aria-label="Gela health" style={{
      position: "fixed", left: 20, bottom: 48, zIndex: 70,
      width: "min(420px, calc(100vw - 40px))", maxHeight: "min(570px, calc(100vh - 110px))",
      overflowY: "auto", color: "#f0e8e6", background: "rgba(17, 12, 13, 0.97)",
      border: "1px solid #9d443e", borderRadius: 8, boxShadow: "0 20px 60px #000b",
      padding: "18px 20px", userSelect: "text",
    }}>
      <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid #61302e", paddingBottom: 11 }}>
        <div style={{ flex: 1, color: "#e9867a", letterSpacing: "0.2em", fontWeight: 700, fontSize: 12 }}>GELA / SYSTEM HEALTH</div>
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close health panel" style={{
          border: 0, color: "#e2c1bc", background: "transparent", fontSize: 22, cursor: "pointer",
        }}>×</button>
      </div>
      <div style={{ fontSize: 11, lineHeight: 1.55, color: "#b8a39f", padding: "12px 0" }}>
        Worker and mobile-link heartbeats are independent. The last state and supervisor details are snapshots; they do not prove those processes are still running.
      </div>
      {rows.map(([label, value]) => (
        <div key={label} style={{ borderTop: "1px solid #3f2625", padding: "9px 0", display: "grid", gridTemplateColumns: "92px 1fr", gap: 10 }}>
          <span style={{ color: "#d99583", fontSize: 11 }}>{label}</span>
          <span style={{ color: "#efe1dd", fontSize: 11, overflowWrap: "anywhere" }}>{value}</span>
        </div>
      ))}
    </div>
  );
}
