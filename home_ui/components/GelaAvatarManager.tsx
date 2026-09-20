"use client";

import { useEffect, useRef, useState } from "react";

type AvatarConfig = { custom: boolean; name: string; version: number };

function announceAvatar(url?: string) {
  window.dispatchEvent(new CustomEvent("gela-avatar-changed", { detail: { url } }));
}

export default function GelaAvatarManager({ onClose }: { onClose: () => void }) {
  const [config, setConfig] = useState<AvatarConfig | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const previewUrl = useRef<string | null>(null);

  const loadConfig = () => fetch("/api/avatar", { cache: "no-store" }).then((r) => r.json()).then(setConfig);
  useEffect(() => { loadConfig().catch(() => setMessage("Avatar settings could not be loaded.")); }, []);
  useEffect(() => () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); }, []);

  const choose = (next: File | null) => {
    setMessage("");
    setFile(next);
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current = next ? URL.createObjectURL(next) : null;
    announceAvatar(previewUrl.current || undefined);
  };
  const apply = async () => {
    if (!file) return;
    setBusy(true); setMessage("Validating and installing hologram…");
    try {
      const body = new FormData(); body.append("avatar", file);
      const response = await fetch("/api/avatar", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Avatar could not be installed");
      setConfig(data); setFile(null); setMessage(`${data.name} is now active.`);
      announceAvatar(`/api/avatar?model=active&v=${data.version}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Avatar could not be installed"); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true); setMessage("Restoring default avatar…");
    try {
      const response = await fetch("/api/avatar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "reset" }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Default could not be restored");
      setConfig(data); setFile(null); setMessage("Default Gela avatar restored."); announceAvatar("/models/head.glb");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Default could not be restored"); }
    finally { setBusy(false); }
  };
  const close = () => { if (file) announceAvatar(); onClose(); };

  return <div style={{ padding: 20, display: "grid", gap: 16 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ flex: 1 }}>
        <div style={{ color: "#00ffff", fontSize: 11, fontWeight: 700, letterSpacing: ".18em" }}>AVATAR HOLOGRAM</div>
        <div style={{ marginTop: 5, color: "rgba(232,244,248,.58)", fontSize: 11 }}>Active: {config?.name || "Loading…"}</div>
      </div>
      <button onClick={close} aria-label="Back to Gela Control" className="hex-button">BACK</button>
    </div>
    <label className="avatar-dropzone">
      <input type="file" accept=".glb,model/gltf-binary" onChange={(e) => choose(e.target.files?.[0] || null)} style={{ position: "absolute", opacity: 0, pointerEvents: "none" }} />
      <span style={{ color: "#00ffc8", letterSpacing: ".14em", fontSize: 12 }}>{file ? file.name : "CHOOSE GLB MODEL"}</span>
      <span style={{ color: "rgba(232,244,248,.46)", fontSize: 10 }}>Maximum 50 MB · preview appears immediately · remains local</span>
    </label>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
      <button disabled={!file || busy} onClick={apply} className="hex-button hex-button-primary">APPLY AVATAR</button>
      <button disabled={busy || !config?.custom} onClick={reset} className="hex-button">RESTORE DEFAULT</button>
      {file && <button disabled={busy} onClick={() => choose(null)} className="hex-button">CANCEL PREVIEW</button>}
    </div>
    {message && <div role="status" style={{ color: message.includes("could not") || message.includes("Only") ? "#ff8b72" : "#00ffc8", fontSize: 11, letterSpacing: ".05em" }}>{message}</div>}
    <div style={{ color: "rgba(232,244,248,.42)", fontSize: 10, lineHeight: 1.55 }}>Gela automatically centers and scales the model, combines all visible meshes, and preserves the current 70,000-particle performance ceiling.</div>
  </div>;
}
