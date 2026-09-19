import { NextRequest, NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const projectRoot = resolve(process.env.GELA_PROJECT_ROOT || resolve(process.cwd(), ".."));
const statusPath = join(process.env.LOCALAPPDATA || "", "Gela", "runtime", "status.json");
const bridgeStatusPath = join(process.env.LOCALAPPDATA || "", "Gela", "mobile", "bridge_status.json");
const workerHeartbeatPath = join(process.env.LOCALAPPDATA || "", "Gela", "runtime", "worker_heartbeat.json");
const supervisorStatusPath = join(process.env.LOCALAPPDATA || "", "Gela", "runtime", "supervisor", "status.json");
const pythonw = join(projectRoot, ".venv", "Scripts", "pythonw.exe");
const gelaExe = join(projectRoot, "Gela.exe");

function localRequest(request: NextRequest): boolean {
  const host = request.headers.get("host") || "";
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(host);
}

function launch(command: string, args: string[], useGela = false): void {
  const child = spawn(command, args, {
    cwd: projectRoot,
    detached: true,
    stdio: "ignore",
    windowsHide: true,
    env: useGela ? { ...process.env, PYTHONPATH: join(projectRoot, "src") } : process.env,
  });
  child.on("error", (error) => console.error("Gela Home launch failed:", error));
  child.unref();
}

export async function GET(request: NextRequest) {
  if (!localRequest(request)) return NextResponse.json({ error: "Local use only" }, { status: 403 });
  let bridgeFresh = false;
  try {
    const bridge = JSON.parse(readFileSync(bridgeStatusPath, "utf8"));
    const ageMs = Date.now() - statSync(bridgeStatusPath).mtimeMs;
    bridgeFresh = bridge.running === true && ageMs >= 0 && ageMs < 5000;
  } catch { /* bridge is unavailable */ }
  let workerFresh = false;
  try {
    const heartbeat = JSON.parse(readFileSync(workerHeartbeatPath, "utf8"));
    const ageMs = Date.now() - statSync(workerHeartbeatPath).mtimeMs;
    workerFresh = Number.isInteger(heartbeat.pid) && ageMs >= 0 && ageMs < 7000;
  } catch { /* worker heartbeat is unavailable, including older installs */ }
  let supervisorState = "unknown";
  let supervisorUpdatedAt: string | null = null;
  try {
    const supervisor = JSON.parse(readFileSync(supervisorStatusPath, "utf8"));
    if (typeof supervisor.state === "string") supervisorState = supervisor.state;
    if (typeof supervisor.updated_at === "string") supervisorUpdatedAt = supervisor.updated_at;
  } catch { /* older installations may have no supervisor */ }
  try {
    const status = JSON.parse(readFileSync(statusPath, "utf8"));
    const reportedAt = Date.parse(String(status.updated_at || ""));
    const reportAgeMs = Date.now() - reportedAt;
    const statusRecent = Number.isFinite(reportedAt) && reportAgeMs >= 0 && reportAgeMs < 10_000;
    // The bridge file contains pairing secrets: expose only its fresh heartbeat.
    // A worker status snapshot may be old even while the bridge remains live.
    return NextResponse.json({ online: true, status: status.status, updatedAt: status.updated_at,
      fresh: bridgeFresh, bridgeFresh, workerFresh, statusRecent, supervisorState, supervisorUpdatedAt,
      microphone: status.microphone, microphoneState: status.microphone_state,
      models: status.models, catalog: status.catalog,
      lastCommand: status.last_command, lastExecution: status.last_execution },
      { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ online: false, fresh: bridgeFresh, bridgeFresh, workerFresh, statusRecent: false,
      supervisorState, supervisorUpdatedAt, status: "offline" },
      { headers: { "Cache-Control": "no-store" } });
  }
}

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin") || request.headers.get("referer");
  let sameOrigin = false;
  try {
    sameOrigin = Boolean(origin && new URL(origin).host === request.headers.get("host") && new URL(origin).protocol === "http:");
  } catch { /* reject missing or malformed origin */ }
  if (!localRequest(request) || !sameOrigin ||
      !request.headers.get("content-type")?.startsWith("application/json")) {
    return NextResponse.json({ error: "Local same-origin request required" }, { status: 403 });
  }
  let action: unknown;
  try { action = (await request.json()).action; }
  catch { return NextResponse.json({ error: "Invalid request" }, { status: 400 }); }

  const gelaWindows: Record<string, { module: string; flag: string }> = {
    notes: { module: "voice_assistant.notes_window", flag: "--notes-window" },
    mobile: { module: "voice_assistant.mobile_connection_window", flag: "--mobile-connection" },
    settings: { module: "voice_assistant.settings_window", flag: "--settings-window" },
    diagnostics: { module: "voice_assistant.diagnostics", flag: "--diagnostics" },
    voice_names: { module: "voice_assistant.alias_manager", flag: "--alias-manager" },
    routines: { module: "voice_assistant.routine_manager", flag: "--routine-manager" },
    logs: { module: "voice_assistant.logs_window", flag: "--logs-window" },
  };
  if (typeof action === "string" && Object.hasOwn(gelaWindows, action)) {
    if (existsSync(gelaExe)) {
      launch(gelaExe, [gelaWindows[action].flag]);
    } else if (existsSync(pythonw)) {
      launch(pythonw, ["-m", gelaWindows[action].module], true);
    } else {
      return NextResponse.json({ error: "Gela's PC runtime was not found" }, { status: 503 });
    }
  } else if (action === "this_pc") {
    launch("explorer.exe", ["shell:MyComputerFolder"]);
  } else if (action === "apps") {
    launch("explorer.exe", ["shell:AppsFolder"]);
  } else if (action === "documents") {
    launch("powershell.exe", ["-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
      "$path=[Environment]::GetFolderPath('MyDocuments'); if (-not $path) { throw 'Documents folder was not found' }; Start-Process explorer.exe -ArgumentList $path"]);
  } else if (action === "downloads") {
    launch("explorer.exe", ["shell:Downloads"]);
  } else if (action === "music") {
    launch("explorer.exe", ["shell:My Music"]);
  } else if (action === "games") {
    launch("explorer.exe", ["steam://open/games"]);
  } else if (action === "search") {
    launch("explorer.exe", ["search-ms:"]);
  } else if (action === "task_manager") {
    launch("taskmgr.exe", []);
  } else if (action === "recycle_bin") {
    launch("explorer.exe", ["shell:RecycleBinFolder"]);
  } else if (action === "desktop") {
    launch("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll()"]);
  } else {
    return NextResponse.json({ error: "Unknown destination" }, { status: 400 });
  }
  return NextResponse.json({ ok: true });
}
