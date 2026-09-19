import { cpSync, existsSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const standalone = join(root, ".next", "standalone");
if (!existsSync(join(standalone, "server.js"))) {
  throw new Error("Next standalone server was not generated");
}
cpSync(join(root, ".next", "static"), join(standalone, ".next", "static"), { recursive: true, force: true });
cpSync(join(root, "public"), join(standalone, "public"), { recursive: true, force: true });
console.log("Gela Home standalone static assets synchronized");
