import { mkdtemp, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

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
          data: { document_types: [".txt"], image_types: [], all_types: [".txt"] },
        }),
      ),
    );
    const output = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    const code = await run(["node", "unifiles", "--output", "json", "status"]);
    expect(code).toBe(0);
    expect(output.mock.calls.flat().join("")).toContain('"ok": true');
  });
});
