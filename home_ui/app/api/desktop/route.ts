import { NextRequest, NextResponse } from "next/server";
import { execFile } from "node:child_process";
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { promisify } from "node:util";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const runFile = promisify(execFile);

function localRequest(request: NextRequest): boolean {
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(request.headers.get("host") || "");
}

export async function GET(request: NextRequest) {
  if (!localRequest(request)) return NextResponse.json({ error: "Local use only" }, { status: 403 });
  try {
    // Windows resolves this known folder even when Desktop is redirected to OneDrive.
    const { stdout } = await runFile("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command",
      "[Environment]::GetFolderPath('DesktopDirectory')"], { windowsHide: true, timeout: 5000 });
    const personal = stdout.trim();
    if (!personal) throw new Error("Desktop folder unavailable");
    const publicDesktop = join(process.env.PUBLIC || "C:\\Users\\Public", "Desktop");
    const locations = [{ path: personal, source: "Personal" }, { path: publicDesktop, source: "Public" }];
    const items = locations.flatMap(({ path, source }) => {
      try {
        return readdirSync(path, { withFileTypes: true })
          .filter((entry) => entry.name.toLowerCase() !== "desktop.ini")
          .map((entry) => ({
            name: entry.name,
            source,
            type: entry.isDirectory() ? "folder" : entry.name.toLowerCase().endsWith(".lnk") ? "shortcut" : "file",
          }));
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
        throw error;
      }
    }).sort((a, b) => a.name.localeCompare(b.name));
    return NextResponse.json({ items }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Windows Desktop items could not be read" }, { status: 503 });
  }
}
