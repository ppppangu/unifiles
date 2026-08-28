import { chmod, mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { stdin, stderr } from "node:process";
import { emitKeypressEvents } from "node:readline";

import { parse, stringify } from "smol-toml";

export interface Profile {
  baseUrl: string;
  apiKey?: string;
}

interface ConfigFile {
  currentProfile: string;
  profiles: Record<string, Profile>;
}

const emptyConfig = (): ConfigFile => ({ currentProfile: "default", profiles: {} });

export function configPath(): string {
  const root = process.env.XDG_CONFIG_HOME ?? join(homedir(), ".config");
  return join(root, "unifiles", "config.toml");
}

export async function loadConfig(): Promise<ConfigFile> {
  try {
    const wire = parse(await readFile(configPath(), "utf8")) as Record<string, unknown>;
    const profiles: Record<string, Profile> = {};
    const rawProfiles = wire.profiles;
    if (rawProfiles && typeof rawProfiles === "object") {
      for (const [name, raw] of Object.entries(rawProfiles)) {
        if (!raw || typeof raw !== "object") continue;
        const record = raw as Record<string, unknown>;
        if (typeof record.base_url !== "string") continue;
        profiles[name] = {
          baseUrl: record.base_url,
          ...(typeof record.api_key === "string" ? { apiKey: record.api_key } : {}),
        };
      }
    }
    return {
      currentProfile: typeof wire.current_profile === "string" ? wire.current_profile : "default",
      profiles,
    };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return emptyConfig();
    throw error;
  }
}

export async function saveConfig(config: ConfigFile): Promise<void> {
  const path = configPath();
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  const payload = stringify({
    current_profile: config.currentProfile,
    profiles: Object.fromEntries(
      Object.entries(config.profiles).map(([name, profile]) => [
        name,
        {
          base_url: profile.baseUrl,
          ...(profile.apiKey ? { api_key: profile.apiKey } : {}),
        },
      ]),
    ),
  });
  const temporary = `${path}.${process.pid}.tmp`;
  await writeFile(temporary, payload, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, path);
  await chmod(path, 0o600);
}

export async function setProfile(name: string, profile: Profile): Promise<void> {
  const config = await loadConfig();
  config.profiles[name] = profile;
  if (!config.profiles[config.currentProfile]) config.currentProfile = name;
  await saveConfig(config);
}

export async function useProfile(name: string): Promise<void> {
  const config = await loadConfig();
  if (!config.profiles[name]) throw new Error(`Profile '${name}' does not exist`);
  config.currentProfile = name;
  await saveConfig(config);
}

export async function deleteProfile(name: string): Promise<void> {
  const config = await loadConfig();
  if (!config.profiles[name]) throw new Error(`Profile '${name}' does not exist`);
  delete config.profiles[name];
  if (config.currentProfile === name) config.currentProfile = Object.keys(config.profiles)[0] ?? "default";
  await saveConfig(config);
}

export async function resolveProfile(
  selected?: string,
  baseUrlOverride?: string,
): Promise<{ name: string; baseUrl: string; apiKey?: string }> {
  const config = await loadConfig();
  const name = selected ?? process.env.UNIFILES_PROFILE ?? config.currentProfile;
  const profile = config.profiles[name];
  const baseUrl =
    baseUrlOverride ??
    process.env.UNIFILES_BASE_URL ??
    profile?.baseUrl ??
    "https://api.unifiles.dev/v1";
  const apiKey = process.env.UNIFILES_API_KEY ?? profile?.apiKey;
  return { name, baseUrl, ...(apiKey ? { apiKey } : {}) };
}

export async function readAllStdin(): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const chunk of stdin) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  return Buffer.concat(chunks);
}

export async function promptSecret(prompt = "API key: "): Promise<string> {
  if (!stdin.isTTY) throw new Error("Use UNIFILES_API_KEY or --api-key-stdin in non-interactive mode");
  emitKeypressEvents(stdin);
  stdin.setRawMode(true);
  stderr.write(prompt);
  return new Promise((resolve, reject) => {
    let value = "";
    const cleanup = (): void => {
      stdin.off("keypress", onKey);
      stdin.setRawMode(false);
      stdin.pause();
      stderr.write("\n");
    };
    const onKey = (text: string, key: { name?: string; ctrl?: boolean }): void => {
      if (key.ctrl && key.name === "c") {
        cleanup();
        reject(new Error("Cancelled"));
        return;
      }
      if (key.name === "return" || key.name === "enter") {
        cleanup();
        resolve(value);
        return;
      }
      if (key.name === "backspace") {
        value = value.slice(0, -1);
        return;
      }
      if (text && !key.ctrl) value += text;
    };
    stdin.on("keypress", onKey);
  });
}
