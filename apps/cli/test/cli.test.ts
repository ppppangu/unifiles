import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import { configPath, resolveProfile, setProfile } from "../src/config.js";
import { createProgram, run } from "../src/index.js";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  delete process.env.XDG_CONFIG_HOME;
  delete process.env.UNIFILES_API_KEY;
  delete process.env.UNIFILES_BASE_URL;
});

describe("CLI", () => {
  it("exposes every resource command group", () => {
    const names = createProgram().commands.map((command) => command.name());
    expect(names).toEqual(
      expect.arrayContaining(["config", "status", "files", "extractions", "kb", "webhooks", "api-keys", "usage"]),
    );
  });

  it("writes XDG profiles with owner-only permissions and applies env precedence", async () => {
    process.env.XDG_CONFIG_HOME = await mkdtemp(join(tmpdir(), "unifiles-cli-"));
    await setProfile("local", { baseUrl: "http://localhost:8088", apiKey: "profile-key" });
    const metadata = await stat(configPath());
    expect(metadata.mode & 0o777).toBe(0o600);
    expect(await readFile(configPath(), "utf8")).toContain("profile-key");

    process.env.UNIFILES_API_KEY = "env-key";
    process.env.UNIFILES_BASE_URL = "http://override.test";
    const profile = await resolveProfile("local");
    expect(profile.apiKey).toBe("env-key");
    expect(profile.baseUrl).toBe("http://override.test");
  });

  it("uses the SDK for status and returns JSON", async () => {
    process.env.XDG_CONFIG_HOME = await mkdtemp(join(tmpdir(), "unifiles-cli-"));
    process.env.UNIFILES_API_KEY = "sk_test";
    process.env.UNIFILES_BASE_URL = "http://example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({
          success: true,
          data: { status: "ok", version: "0.1.0" },
        }),
      ),
    );
    const output = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    const code = await run(["node", "unifiles", "--output", "json", "status"]);
    expect(code).toBe(0);
    expect(output.mock.calls.flat().join("")).toContain('"ok": true');
  });

  it("runs through the npm bin symlink", () => {
    const executable = fileURLToPath(
      new URL(
        `../../../node_modules/.bin/unifiles${process.platform === "win32" ? ".cmd" : ""}`,
        import.meta.url,
      ),
    );
    const result = spawnSync(executable, ["--help"], {
      encoding: "utf8",
      shell: process.platform === "win32",
    });

    expect(result.status, result.stderr).toBe(0);
    expect(result.stdout).toContain("Unix-style client for the Unifiles API");
  });
});
