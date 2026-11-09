import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { acquireLock, type LockHolder } from "../e2e/machine-lock.ts";

function lockPath(): string {
  return join(mkdtempSync(join(tmpdir(), "machine-lock-test-")), "e2e.lock");
}

function fakeHolder(path: string, pid: number) {
  mkdirSync(path);
  writeFileSync(join(path, "holder.json"), JSON.stringify({ pid, cwd: "/elsewhere" }));
}

test("a free lock is taken at once and released", async () => {
  const path = lockPath();
  const release = await acquireLock(path);
  assert.ok(existsSync(path));
  release();
  assert.ok(!existsSync(path));
});

test("a second run waits until the first releases the lock", async () => {
  const path = lockPath();
  const releaseFirst = await acquireLock(path);
  let secondHasLock = false;
  const second = acquireLock(path, { pollMs: 5 }).then((release) => {
    secondHasLock = true;
    return release;
  });
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.equal(secondHasLock, false);
  releaseFirst();
  const releaseSecond = await second;
  assert.ok(existsSync(path));
  releaseSecond();
});

test("the waiting run is told who holds the lock, once", async () => {
  const path = lockPath();
  fakeHolder(path, process.ppid);
  const told: LockHolder[] = [];
  const waiting = acquireLock(path, { pollMs: 5, onWait: (holder) => told.push(holder) });
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.deepEqual(told, [{ pid: process.ppid, cwd: "/elsewhere" }]);
  // The fake holder never ends, so free the lock by hand.
  rmSync(path, { recursive: true });
  (await waiting)();
});

test("a lock left by a run that has ended is taken over", async () => {
  const path = lockPath();
  const ended = spawnSync(process.execPath, ["-e", ""]);
  fakeHolder(path, ended.pid!);
  const release = await acquireLock(path, { pollMs: 5 });
  release();
  assert.ok(!existsSync(path));
});

test("releasing a lock another run has since taken leaves it alone", async () => {
  const path = lockPath();
  const release = await acquireLock(path);
  rmSync(path, { recursive: true });
  fakeHolder(path, process.ppid);
  release();
  assert.ok(existsSync(path));
});
