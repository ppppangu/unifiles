#!/usr/bin/env node

import { realpathSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import process from "node:process";

import {
  AuthenticationError,
  NotFoundError,
  PermissionError,
  ProcessingError,
  RateLimitError,
  TimeoutError,
  TransportError,
  UnifilesClient,
  UnifilesError,
  ValidationError,
} from "@wyy/unifiles";
import { Command, CommanderError, Option } from "commander";

import {
  configPath,
  deleteProfile,
  loadConfig,
  promptSecret,
  readAllStdin,
  resolveProfile,
  saveConfig,
  setProfile,
  useProfile,
} from "./config.js";
import { diagnostic, printData, type OutputFormat } from "./output.js";

interface GlobalOptions {
  profile?: string;
  baseUrl?: string;
  output: OutputFormat;
  quiet?: boolean;
  debug?: boolean;
}

const globalOptions = (command: Command): GlobalOptions => command.optsWithGlobals<GlobalOptions>();

const clientFor = async (command: Command): Promise<UnifilesClient> => {
  const options = globalOptions(command);
  const profile = await resolveProfile(options.profile, options.baseUrl);
  return new UnifilesClient({
    baseUrl: profile.baseUrl,
    ...(profile.apiKey ? { apiKey: profile.apiKey } : {}),
  });
};

const emit = (command: Command, data: unknown): void => printData(data, globalOptions(command).output);

const parseJson = async <T>(value: string | undefined, fallback: T): Promise<T> => {
  if (!value) return fallback;
  const text = value.startsWith("@") ? await readFile(value.slice(1), "utf8") : value;
  return JSON.parse(text) as T;
};

const waitOptions = (options: { timeout?: string; pollInterval?: string }) => ({
  timeoutMs: Number(options.timeout ?? 300) * 1000,
  pollIntervalMs: Number(options.pollInterval ?? 2) * 1000,
});

export function createProgram(): Command {
  const program = new Command()
    .name("unifiles")
    .description("Unix-style client for the Unifiles API")
    .version("0.1.0")
    .option("--profile <name>", "use a named profile")
    .option("--base-url <url>", "override the API base URL")
    .addOption(
      new Option("-o, --output <format>", "output format")
        .choices(["auto", "table", "json", "jsonl", "raw"])
        .default("auto"),
    )
    .option("-q, --quiet", "suppress progress diagnostics")
    .option("--debug", "show diagnostic errors");
  program.exitOverride();

  const config = program.command("config").description("manage API profiles");
  config
    .command("set")
    .argument("[name]", "profile name", "default")
    .requiredOption("--base-url <url>", "API base URL")
    .option("--api-key-stdin", "read the API key from stdin")
    .action(async (name: string, options: { baseUrl: string; apiKeyStdin?: boolean }, command: Command) => {
      const apiKey = options.apiKeyStdin
        ? (await readAllStdin()).toString("utf8").trim()
        : process.env.UNIFILES_API_KEY ?? (await promptSecret());
      await setProfile(name, { baseUrl: options.baseUrl, apiKey });
      emit(command, { profile: name, baseUrl: options.baseUrl, saved: true });
    });
  config.command("list").action(async (_options: unknown, command: Command) => {
    const value = await loadConfig();
    emit(
      command,
      Object.entries(value.profiles).map(([name, profile]) => ({
        name,
        current: name === value.currentProfile,
        baseUrl: profile.baseUrl,
        hasApiKey: Boolean(profile.apiKey),
      })),
    );
  });
  config
    .command("show")
    .argument("[name]")
    .action(async (name: string | undefined, _options: unknown, command: Command) => {
      const value = await loadConfig();
      const selected = name ?? value.currentProfile;
      const profile = value.profiles[selected];
      if (!profile) throw new Error(`Profile '${selected}' does not exist`);
      emit(command, { name: selected, baseUrl: profile.baseUrl, apiKey: profile.apiKey ? "********" : null });
    });
  config
    .command("use")
    .argument("<name>")
    .action(async (name: string, _options: unknown, command: Command) => {
      await useProfile(name);
      emit(command, { profile: name, current: true });
    });
  config
    .command("delete")
    .argument("<name>")
    .action(async (name: string, _options: unknown, command: Command) => {
      await deleteProfile(name);
      emit(command, { profile: name, deleted: true });
    });

  program.command("status").action(async (_options: unknown, command: Command) => {
    const client = await clientFor(command);
    await client.files.listSupportedTypes();
    emit(command, { ok: true, baseUrl: client.baseUrl });
  });

  const files = program.command("files").description("manage source files");
  files
    .command("upload")
    .argument("<path>", "file path or - for stdin")
    .option("--filename <name>", "filename for stdin or byte uploads")
    .option("--content-type <type>", "MIME type")
    .option("--metadata <json>", "JSON object or @file")
    .option("--tag <tag...>", "one or more tags")
    .action(async (path: string, options: Record<string, unknown>, command: Command) => {
      const client = await clientFor(command);
      const metadata = await parseJson<Record<string, unknown>>(options.metadata as string | undefined, {});
      diagnostic(`Uploading ${path}...`, globalOptions(command).quiet);
      const input = path === "-" ? await readAllStdin() : path;
      const file = await client.files.upload(input, {
        ...(options.filename ? { filename: String(options.filename) } : {}),
        ...(options.contentType ? { contentType: String(options.contentType) } : {}),
        metadata,
        tags: (options.tag as string[] | undefined) ?? [],
      });
      emit(command, file);
    });
  files
    .command("list")
    .option("--limit <n>", "page size", "50")
    .option("--offset <n>", "page offset", "0")
    .option("--tag <tag...>")
    .option("--content-type <type>")
    .action(async (options: Record<string, unknown>, command: Command) => {
      const client = await clientFor(command);
      emit(
        command,
        await client.files.list({
          limit: Number(options.limit),
          offset: Number(options.offset),
          ...(options.tag ? { tags: options.tag as string[] } : {}),
          ...(options.contentType ? { contentType: String(options.contentType) } : {}),
        }),
      );
    });
  files
    .command("get")
    .argument("<file-id>")
    .action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).files.get(id)));
  files
    .command("download")
    .argument("<file-id>")
    .option("-o, --output-file <path>", "destination path or - for stdout", "-")
    .action(async (id: string, options: { outputFile: string }, command: Command) => {
      const data = await (await clientFor(command)).files.download(id);
      if (options.outputFile === "-") process.stdout.write(data);
      else {
        await writeFile(options.outputFile, data);
        emit(command, { id, path: options.outputFile, bytes: data.byteLength });
      }
    });
  files
    .command("delete")
    .argument("<file-id>")
    .action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).files.delete(id)));
  files.command("types").action(async (_options: unknown, command: Command) => emit(command, await (await clientFor(command)).files.listSupportedTypes()));

  const extractions = program.command("extractions").description("manage extraction tasks");
  extractions
    .command("create")
    .argument("<file-id>")
    .option("--mode <mode>", "simple, normal, or advanced", "normal")
    .option("--options <json>", "JSON object or @file")
    .option("--wait", "wait until completion")
    .option("--timeout <seconds>", "wait timeout", "300")
    .option("--poll-interval <seconds>", "poll interval", "2")
    .action(async (fileId: string, options: Record<string, unknown>, command: Command) => {
      const client = await clientFor(command);
      let extraction = await client.extractions.create(fileId, {
        mode: String(options.mode),
        options: await parseJson<Record<string, unknown>>(options.options as string | undefined, {}),
      });
      if (options.wait) extraction = await extraction.wait(waitOptions(options as never));
      emit(command, extraction);
    });
  extractions
    .command("get")
    .argument("<extraction-id>")
    .option("--wait")
    .option("--timeout <seconds>", "wait timeout", "300")
    .option("--poll-interval <seconds>", "poll interval", "2")
    .action(async (id: string, options: Record<string, unknown>, command: Command) => {
      let extraction = await (await clientFor(command)).extractions.get(id);
      if (options.wait) extraction = await extraction.wait(waitOptions(options as never));
      emit(command, extraction);
    });
  extractions
    .command("list")
    .argument("<file-id>")
    .option("--limit <n>", "page size", "50")
    .option("--offset <n>", "page offset", "0")
    .action(async (fileId: string, options: Record<string, unknown>, command: Command) =>
      emit(command, await (await clientFor(command)).extractions.list(fileId, { limit: Number(options.limit), offset: Number(options.offset) })),
    );

  const kb = program.command("kb").alias("knowledge-bases").description("manage knowledge bases");
  kb.command("create")
    .argument("<name>")
    .option("--description <text>")
    .option("--chunking <json>", "JSON object or @file")
    .option("--metadata <json>", "JSON object or @file")
    .action(async (name: string, options: Record<string, unknown>, command: Command) =>
      emit(
        command,
        await (await clientFor(command)).knowledgeBases.create(name, {
          ...(options.description ? { description: String(options.description) } : {}),
          chunkingStrategy: await parseJson<Record<string, unknown>>(options.chunking as string | undefined, {}),
          metadata: await parseJson<Record<string, unknown>>(options.metadata as string | undefined, {}),
        }),
      ),
    );
  kb.command("list")
    .option("--limit <n>", "page size", "50")
    .option("--offset <n>", "page offset", "0")
    .action(async (options: Record<string, unknown>, command: Command) =>
      emit(command, await (await clientFor(command)).knowledgeBases.list({ limit: Number(options.limit), offset: Number(options.offset) })),
    );
  kb.command("get").argument("<kb-id>").action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).knowledgeBases.get(id)));
  kb.command("update")
    .argument("<kb-id>")
    .option("--name <name>")
    .option("--description <text>")
    .option("--chunking <json>")
    .option("--metadata <json>")
    .action(async (id: string, options: Record<string, unknown>, command: Command) =>
      emit(
        command,
        await (await clientFor(command)).knowledgeBases.update(id, {
          ...(options.name ? { name: String(options.name) } : {}),
          ...(options.description ? { description: String(options.description) } : {}),
          ...(options.chunking ? { chunkingStrategy: await parseJson(String(options.chunking), {}) } : {}),
          ...(options.metadata ? { metadata: await parseJson(String(options.metadata), {}) } : {}),
        }),
      ),
    );
  kb.command("delete").argument("<kb-id>").action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).knowledgeBases.delete(id)));
  kb.command("search")
    .argument("<kb-id>")
    .argument("<query>")
    .option("--top-k <n>", "maximum results", "5")
    .option("--threshold <n>", "minimum score", "0")
    .option("--filter <json>")
    .action(async (id: string, query: string, options: Record<string, unknown>, command: Command) =>
      emit(command, await (await clientFor(command)).knowledgeBases.search(id, query, {
        topK: Number(options.topK),
        threshold: Number(options.threshold),
        filter: await parseJson<Record<string, unknown>>(options.filter as string | undefined, {}),
      })),
    );
  kb.command("hybrid-search")
    .argument("<kb-id>")
    .argument("<query>")
    .option("--top-k <n>", "maximum results", "5")
    .option("--vector-weight <n>", "vector score weight", "0.7")
    .option("--keyword-weight <n>", "keyword score weight", "0.3")
    .action(async (id: string, query: string, options: Record<string, unknown>, command: Command) =>
      emit(command, await (await clientFor(command)).knowledgeBases.hybridSearch(id, query, {
        topK: Number(options.topK),
        vectorWeight: Number(options.vectorWeight),
        keywordWeight: Number(options.keywordWeight),
      })),
    );

  const documents = kb.command("documents").description("manage indexed documents");
  documents.command("add")
    .argument("<kb-id>")
    .argument("<file-id>")
    .option("--title <title>")
    .option("--metadata <json>")
    .option("--wait")
    .option("--timeout <seconds>", "wait timeout", "300")
    .option("--poll-interval <seconds>", "poll interval", "2")
    .action(async (kbId: string, fileId: string, options: Record<string, unknown>, command: Command) => {
      const client = await clientFor(command);
      let document = await client.knowledgeBases.documents.create(kbId, fileId, {
        ...(options.title ? { title: String(options.title) } : {}),
        metadata: await parseJson<Record<string, unknown>>(options.metadata as string | undefined, {}),
      });
      if (options.wait) document = await document.wait(waitOptions(options as never));
      emit(command, document);
    });
  documents.command("list")
    .argument("<kb-id>")
    .option("--limit <n>", "page size", "50")
    .option("--offset <n>", "page offset", "0")
    .action(async (kbId: string, options: Record<string, unknown>, command: Command) =>
      emit(command, await (await clientFor(command)).knowledgeBases.documents.list(kbId, { limit: Number(options.limit), offset: Number(options.offset) })),
    );
  documents.command("get").argument("<kb-id>").argument("<document-id>").action(async (kbId: string, id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).knowledgeBases.documents.get(kbId, id)));
  documents.command("delete").argument("<kb-id>").argument("<document-id>").action(async (kbId: string, id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).knowledgeBases.documents.delete(kbId, id)));

  const webhooks = program.command("webhooks").description("manage webhooks");
  webhooks.command("create").argument("<url>").requiredOption("--event <event...>").option("--description <text>").action(async (url: string, options: Record<string, unknown>, command: Command) => emit(command, await (await clientFor(command)).webhooks.create(url, options.event as string[], {
    ...(options.description ? { description: String(options.description) } : {}),
  })));
  webhooks.command("list").option("--limit <n>", "page size", "50").option("--offset <n>", "page offset", "0").action(async (options: Record<string, unknown>, command: Command) => emit(command, await (await clientFor(command)).webhooks.list({ limit: Number(options.limit), offset: Number(options.offset) })));
  webhooks.command("get").argument("<id>").action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).webhooks.get(id)));
  webhooks.command("update").argument("<id>").option("--url <url>").option("--event <event...>").option("--description <text>").option("--enable").option("--disable").action(async (id: string, options: Record<string, unknown>, command: Command) => emit(command, await (await clientFor(command)).webhooks.update(id, {
    ...(options.url ? { url: String(options.url) } : {}),
    ...(options.event ? { events: options.event as string[] } : {}),
    ...(options.description ? { description: String(options.description) } : {}),
    ...(options.enable ? { enabled: true } : {}),
    ...(options.disable ? { enabled: false } : {}),
  })));
  webhooks.command("delete").argument("<id>").action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).webhooks.delete(id)));

  const apiKeys = program.command("api-keys").description("manage API keys");
  apiKeys.command("create").argument("<name>").option("--scope <scope...>").option("--expires-at <iso-date>").action(async (name: string, options: Record<string, unknown>, command: Command) => emit(command, await (await clientFor(command)).apiKeys.create(name, {
    ...(options.scope ? { scopes: options.scope as string[] } : {}),
    ...(options.expiresAt ? { expiresAt: String(options.expiresAt) } : {}),
  })));
  apiKeys.command("list").option("--limit <n>", "page size", "50").option("--offset <n>", "page offset", "0").action(async (options: Record<string, unknown>, command: Command) => emit(command, await (await clientFor(command)).apiKeys.list({ limit: Number(options.limit), offset: Number(options.offset) })));
  apiKeys.command("revoke").argument("<id>").action(async (id: string, _options: unknown, command: Command) => emit(command, await (await clientFor(command)).apiKeys.revoke(id)));

  const usage = program.command("usage").description("inspect usage and limits");
  usage.command("stats").action(async (_options: unknown, command: Command) => emit(command, await (await clientFor(command)).usage.getStats()));
  usage.command("limits").action(async (_options: unknown, command: Command) => emit(command, await (await clientFor(command)).usage.getLimits()));

  return program;
}

const exitCode = (error: unknown): number => {
  if (error instanceof AuthenticationError || error instanceof PermissionError) return 3;
  if (error instanceof NotFoundError) return 4;
  if (error instanceof RateLimitError) return 5;
  if (error instanceof ProcessingError || error instanceof TimeoutError) return 6;
  if (error instanceof TransportError || (error instanceof UnifilesError && (error.statusCode ?? 0) >= 500)) return 7;
  if (error instanceof ValidationError || error instanceof SyntaxError || error instanceof TypeError) return 2;
  return 2;
};

export async function run(argv = process.argv): Promise<number> {
  const program = createProgram();
  try {
    await program.parseAsync(argv);
    return 0;
  } catch (error) {
    if (error instanceof CommanderError && error.exitCode === 0) return 0;
    const options = program.opts<GlobalOptions>();
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`${message}\n`);
    if (options.debug && error instanceof Error && error.stack) process.stderr.write(`${error.stack}\n`);
    return exitCode(error);
  }
}

const isMainModule = (moduleUrl: string, argvPath: string | undefined): boolean => {
  if (!argvPath) return false;
  try {
    return realpathSync(fileURLToPath(moduleUrl)) === realpathSync(argvPath);
  } catch {
    return moduleUrl === pathToFileURL(argvPath).href;
  }
};

if (isMainModule(import.meta.url, process.argv[1])) {
  process.exitCode = await run();
}
