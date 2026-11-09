import { mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

export type LockHolder = { pid: number; cwd: string };

/**
 * Take the lock folder at `path`, waiting while a live process holds it, and
 * return the function that releases it. A lock whose holder has ended is taken
 * over. The folder is filled first and renamed into place, so a lock that
 * exists always names its holder.
 */
export async function acquireLock(
  path: string,
  { pollMs = 2_000, onWait }: { pollMs?: number; onWait?: (holder: LockHolder) => void } = {},
): Promise<() => void> {
  const me: LockHolder = { pid: process.pid, cwd: process.cwd() };
  let told = false;
  for (;;) {
    const draft = mkdtempSync(join(dirname(path), ".lock-draft-"));
    writeFileSync(join(draft, "holder.json"), JSON.stringify(me));
    try {
      renameSync(draft, path);
      return () => {
        if (readHolder(path)?.pid === me.pid) rmSync(path, { recursive: true, force: true });
      };
    } catch (error) {
      rmSync(draft, { recursive: true, force: true });
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "ENOTEMPTY" && code !== "EEXIST") throw error;
    }
    const holder = readHolder(path);
    if (holder && !isAlive(holder.pid)) {
      rmSync(path, { recursive: true, force: true });
      continue;
    }
    if (holder && !told) {
      onWait?.(holder);
      told = true;
    }
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
}

function readHolder(path: string): LockHolder | null {
  try {
    return JSON.parse(readFileSync(join(path, "holder.json"), "utf8"));
  } catch {
    return null;
  }
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}
