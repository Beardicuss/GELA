import { NextRequest, NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { join, resolve } from "node:path";
import { promisify } from "node:util";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const runFile = promisify(execFile);
const projectRoot = resolve(process.env.GELA_PROJECT_ROOT || resolve(process.cwd(), ".."));
const catalogPath = join(process.env.LOCALAPPDATA || "", "Gela", "config", "apps.json");
const python = join(projectRoot, ".venv", "Scripts", "python.exe");
const gelaExe = join(projectRoot, "Gela.exe");
type Kind = "apps" | "games" | "media" | "browsers";
type Entry = { name: string; launch_type: string; launch_value: string };

const BROWSER_NAMES = /\b(chrome|edge|firefox|brave|opera|vivaldi|chromium|waterfox|librewolf|tor browser|arc)\b/i;

function isBrowser(entry: Entry): boolean {
  if (entry.launch_type !== "app_id") return false;
  const target = entry.launch_value.trim().toLowerCase();
  const executable = target.split(/[\\/]/).pop()?.replace(/\.exe$/, "") || target;
  return BROWSER_NAMES.test(entry.name) || /^(chrome|msedge|firefox|brave|brave-browser|opera|vivaldi|chromium|waterfox|librewolf|arc)$/.test(executable);
}

function localRequest(request: NextRequest): boolean {
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(request.headers.get("host") || "");
}

function kindFor(entry: Entry): Kind | null {
  if (entry.launch_type === "file") return "media";
  if (entry.launch_type === "uri" && entry.launch_value.toLowerCase().startsWith("steam://rungameid/")) return "games";
  if (isBrowser(entry)) return "browsers";
  if (entry.launch_type === "app_id") return "apps";
  return null;
}

function entryId(entry: Entry): string {
  return createHash("sha256").update(`${entry.launch_type}\0${entry.launch_value}\0${entry.name}`, "utf8").digest("hex").slice(0, 24);
}

function readEntries(): Entry[] {
  const raw: unknown = JSON.parse(readFileSync(catalogPath, "utf8"));
  if (!Array.isArray(raw)) throw new Error("Catalog is not a list");
  return raw.filter((entry): entry is Entry =>
    typeof entry?.name === "string" && typeof entry?.launch_type === "string" && typeof entry?.launch_value === "string");
}

function validKind(value: string | null): value is Kind {
  return value === "apps" || value === "games" || value === "media" || value === "browsers";
}

export async function GET(request: NextRequest) {
  if (!localRequest(request)) return NextResponse.json({ error: "Local use only" }, { status: 403 });
  const kind = request.nextUrl.searchParams.get("kind");
  if (!validKind(kind)) return NextResponse.json({ error: "Unknown catalog category" }, { status: 400 });
  try {
    const items = readEntries().filter((entry) => kindFor(entry) === kind)
      .map((entry) => ({ id: entryId(entry), name: entry.name }));
    return NextResponse.json({ kind, items }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Gela's app catalog is unavailable" }, { status: 503 });
  }
}

export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin") || request.headers.get("referer");
  let sameOrigin = false;
  try { sameOrigin = Boolean(origin && new URL(origin).host === request.headers.get("host") && new URL(origin).protocol === "http:"); }
  catch { /* reject */ }
  if (!localRequest(request) || !sameOrigin || !request.headers.get("content-type")?.startsWith("application/json")) {
    return NextResponse.json({ error: "Local same-origin request required" }, { status: 403 });
  }
  let input: { kind?: unknown; id?: unknown };
  try { input = await request.json(); }
  catch { return NextResponse.json({ error: "Invalid request" }, { status: 400 }); }
  if (typeof input.kind !== "string" || !validKind(input.kind) ||
      typeof input.id !== "string" || !/^[0-9a-f]{24}$/.test(input.id)) {
    return NextResponse.json({ error: "Invalid catalog selection" }, { status: 400 });
  }
  if (!existsSync(gelaExe) && !existsSync(python)) {
    return NextResponse.json({ error: "Gela's PC runtime was not found" }, { status: 503 });
  }
  try {
    let output;
    // Installed Gela versions before the Browsers hub classified browser app IDs
    // under the general apps allowlist. Keep that secure compatible launch route.
    const launchKind = input.kind === "browsers" ? "apps" : input.kind;
    if (existsSync(gelaExe)) {
      // Windowed PyInstaller executables do not reliably expose stdout pipes.
      const resultDir = join(process.env.LOCALAPPDATA || projectRoot, "Gela", "home", "results");
      mkdirSync(resultDir, { recursive: true });
      const resultPath = join(resultDir, `${randomUUID()}.json`);
      try {
        await runFile(gelaExe, ["--home-catalog-launch", launchKind, input.id, resultPath], {
          cwd: projectRoot, windowsHide: true, timeout: 65_000, maxBuffer: 64 * 1024,
        });
        output = JSON.parse(readFileSync(resultPath, "utf8"));
      } finally {
        rmSync(resultPath, { force: true });
      }
    } else {
      const result = await runFile(python, ["-m", "voice_assistant.home_catalog_launch", launchKind, input.id], {
        cwd: projectRoot,
        env: { ...process.env, PYTHONPATH: join(projectRoot, "src") },
        windowsHide: true, timeout: 65_000, maxBuffer: 64 * 1024,
      });
      output = JSON.parse(result.stdout);
    }
    if (output.ok !== true) throw new Error("Launcher did not confirm success");
    return NextResponse.json({ ok: true, name: output.name, detail: output.detail });
  } catch (error) {
    console.error("Gela Home catalog launch failed:", error);
    return NextResponse.json({ error: "Gela could not verify this launch. Check its logs." }, { status: 500 });
  }
}
