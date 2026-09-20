import { NextRequest, NextResponse } from "next/server";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const avatarRoot = join(process.cwd(), ".runtime", "avatars");
const activePath = join(avatarRoot, "active.glb");
const configPath = join(avatarRoot, "avatar.json");
const maxBytes = 50 * 1024 * 1024;

function localRequest(request: NextRequest): boolean {
  const host = request.headers.get("host") || "";
  return /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(host);
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin") || request.headers.get("referer");
  try {
    return Boolean(origin && new URL(origin).host === request.headers.get("host") && new URL(origin).protocol === "http:");
  } catch { return false; }
}

function activeConfig() {
  if (!existsSync(activePath)) return { custom: false, name: "Default Gela avatar", version: 0 };
  try {
    const saved = JSON.parse(readFileSync(configPath, "utf8"));
    return { custom: true, name: String(saved.name || "Custom avatar"), version: Number(saved.version || 0) };
  } catch {
    return { custom: true, name: "Custom avatar", version: 0 };
  }
}

export async function GET(request: NextRequest) {
  if (!localRequest(request)) return NextResponse.json({ error: "Local use only" }, { status: 403 });
  if (request.nextUrl.searchParams.get("model") === "active") {
    if (!existsSync(activePath)) return NextResponse.json({ error: "No custom avatar" }, { status: 404 });
    return new NextResponse(readFileSync(activePath), {
      headers: { "Content-Type": "model/gltf-binary", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" },
    });
  }
  return NextResponse.json(activeConfig(), { headers: { "Cache-Control": "no-store" } });
}

export async function POST(request: NextRequest) {
  if (!localRequest(request) || !sameOrigin(request)) {
    return NextResponse.json({ error: "Local same-origin request required" }, { status: 403 });
  }
  const contentType = request.headers.get("content-type") || "";
  if (contentType.startsWith("application/json")) {
    let action = "";
    try { action = String((await request.json()).action || ""); } catch { /* invalid below */ }
    if (action !== "reset") return NextResponse.json({ error: "Unknown avatar action" }, { status: 400 });
    const { rmSync } = await import("node:fs");
    rmSync(activePath, { force: true });
    rmSync(configPath, { force: true });
    return NextResponse.json(activeConfig());
  }
  if (!contentType.startsWith("multipart/form-data")) {
    return NextResponse.json({ error: "A GLB file is required" }, { status: 415 });
  }
  const form = await request.formData();
  const file = form.get("avatar");
  if (!(file instanceof File)) return NextResponse.json({ error: "Choose a GLB file" }, { status: 400 });
  if (!file.name.toLowerCase().endsWith(".glb")) return NextResponse.json({ error: "Only .glb models are supported" }, { status: 400 });
  if (file.size < 20 || file.size > maxBytes) return NextResponse.json({ error: "GLB must be between 20 bytes and 50 MB" }, { status: 400 });
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (String.fromCharCode(...bytes.subarray(0, 4)) !== "glTF") {
    return NextResponse.json({ error: "This file is not a valid binary GLB model" }, { status: 400 });
  }
  mkdirSync(avatarRoot, { recursive: true });
  const version = Date.now();
  writeFileSync(activePath, bytes);
  writeFileSync(configPath, JSON.stringify({ name: basename(file.name), version }, null, 2), "utf8");
  return NextResponse.json({ custom: true, name: basename(file.name), version });
}
