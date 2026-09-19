import { NextRequest, NextResponse } from "next/server";
import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, extname, isAbsolute, parse } from "node:path";
import { promisify } from "node:util";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const runFile = promisify(execFile);
const storePath = `${process.env.LOCALAPPDATA || ""}\\Gela\\config\\home_shortcuts.json`;
type Category = "shortcut" | "game";
type Stored = { name: string; path: string; category: Category; slot?: number };

function localRequest(request: NextRequest) { return /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(request.headers.get("host") || ""); }
function sameOrigin(request: NextRequest) {
  const origin = request.headers.get("origin") || request.headers.get("referer");
  try { return Boolean(origin && new URL(origin).host === request.headers.get("host") && new URL(origin).protocol === "http:"); } catch { return false; }
}
function idFor(item: Stored) { return createHash("sha256").update(`${item.category}\0${item.path}`, "utf8").digest("hex").slice(0, 24); }
function readStore(): Stored[] {
  try {
    const raw: unknown = JSON.parse(readFileSync(storePath, "utf8"));
    return Array.isArray(raw) ? raw.filter((item): item is Stored =>
      typeof item?.name === "string" && typeof item?.path === "string" && (item?.category === "shortcut" || item?.category === "game")) : [];
  } catch { return []; }
}
function saveStore(items: Stored[]) {
  mkdirSync(dirname(storePath), { recursive: true });
  const temp = `${storePath}.tmp`;
  writeFileSync(temp, `${JSON.stringify(items, null, 2)}\n`, "utf8");
  renameSync(temp, storePath);
}
function itemType(path: string) {
  if (statSync(path).isDirectory()) return parse(path).root.toLowerCase() === path.toLowerCase() ? "drive" : "folder";
  return extname(path).toLowerCase() === ".exe" ? "program" : "file";
}
function publicItem(item: Stored) { return { id: idFor(item), name: item.name, type: itemType(item.path), slot: item.slot || null }; }
function launch(path: string) {
  const type = itemType(path);
  const child = type === "program" ? spawn(path, [], { detached: true, stdio: "ignore", windowsHide: true })
    : spawn("explorer.exe", [path], { detached: true, stdio: "ignore", windowsHide: true });
  child.unref();
}

export async function GET(request: NextRequest) {
  if (!localRequest(request)) return NextResponse.json({ error: "Local use only" }, { status: 403 });
  const category = request.nextUrl.searchParams.get("category");
  if (category !== "shortcut" && category !== "game") return NextResponse.json({ error: "Unknown category" }, { status: 400 });
  const items = readStore().filter((item) => item.category === category && isAbsolute(item.path) && existsSync(item.path)).map(publicItem);
  return NextResponse.json({ items }, { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: NextRequest) {
  if (!localRequest(request) || !sameOrigin(request) || !request.headers.get("content-type")?.startsWith("application/json"))
    return NextResponse.json({ error: "Local same-origin request required" }, { status: 403 });
  let input: { action?: unknown; category?: unknown; id?: unknown; name?: unknown; slot?: unknown };
  try { input = await request.json(); } catch { return NextResponse.json({ error: "Invalid request" }, { status: 400 }); }
  if (input.category !== "shortcut" && input.category !== "game") return NextResponse.json({ error: "Unknown category" }, { status: 400 });
  const category = input.category;
  let items = readStore();
  if (input.action === "pick_file" || input.action === "pick_folder") {
    const fileScript = "Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.OpenFileDialog;$d.Filter='Programs and files|*.exe;*.lnk;*.*';if($d.ShowDialog() -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$d.FileName}";
    const folderScript = "Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.FolderBrowserDialog;if($d.ShowDialog() -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$d.SelectedPath}";
    const { stdout } = await runFile("powershell.exe", ["-NoProfile", "-STA", "-Command", input.action === "pick_file" ? fileScript : folderScript], { windowsHide: true, timeout: 120_000 });
    const path = stdout.trim();
    if (!path) return NextResponse.json({ ok: true, cancelled: true });
    if (!isAbsolute(path) || !existsSync(path)) return NextResponse.json({ error: "Selected destination is unavailable" }, { status: 400 });
    if (category === "game" && statSync(path).isDirectory()) return NextResponse.json({ error: "Select the game's EXE or shortcut" }, { status: 400 });
    const name = basename(path, extname(path)) || basename(dirname(path)) || path;
    const item: Stored = { name, path, category };
    items = [...items.filter((existing) => idFor(existing) !== idFor(item)), item];
    saveStore(items);
    return NextResponse.json({ ok: true, item: publicItem(item) });
  }
  if (typeof input.id !== "string" || !/^[0-9a-f]{24}$/.test(input.id)) return NextResponse.json({ error: "Invalid shortcut" }, { status: 400 });
  const item = items.find((candidate) => candidate.category === category && idFor(candidate) === input.id);
  if (!item || !isAbsolute(item.path) || !existsSync(item.path)) return NextResponse.json({ error: "Shortcut is unavailable" }, { status: 404 });
  if (input.action === "remove") { saveStore(items.filter((candidate) => idFor(candidate) !== input.id)); return NextResponse.json({ ok: true }); }
  if (input.action === "rename") {
    const name = typeof input.name === "string" ? input.name.trim().slice(0, 40) : "";
    if (!name) return NextResponse.json({ error: "Enter a circle name" }, { status: 400 });
    item.name = name; saveStore(items); return NextResponse.json({ ok: true, item: publicItem(item) });
  }
  if (input.action === "pin") {
    const slot = Number(input.slot);
    if (!Number.isInteger(slot) || slot < 0 || slot > 4) return NextResponse.json({ error: "Invalid circle slot" }, { status: 400 });
    for (const candidate of items) if (candidate.category === "shortcut" && candidate.slot === slot) delete candidate.slot;
    if (slot === 0) delete item.slot; else item.slot = slot;
    saveStore(items); return NextResponse.json({ ok: true, item: publicItem(item) });
  }
  if (input.action === "launch") { launch(item.path); return NextResponse.json({ ok: true, name: item.name }); }
  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
