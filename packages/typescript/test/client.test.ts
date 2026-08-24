import { describe, expect, it, vi } from "vitest";

import { NotFoundError, ServerError, UnifilesClient } from "../src/index.js";

const now = new Date().toISOString();
const envelope = (data: unknown, status = 200): Response =>
  Response.json({ success: true, data }, { status });

describe("UnifilesClient", () => {
  it("maps wire fields to idiomatic TypeScript fields", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      envelope({
        id: "file_1",
        filename: "hello.txt",
        content_type: "text/plain",
        size: 5,
        metadata: {},
        tags: ["demo"],
        created_at: now,
      }),
    );
    const client = new UnifilesClient({
      apiKey: "sk_test",
      baseUrl: "http://example.test",
      maxRetries: 0,
      fetch: fetchMock,
    });

    const file = await client.files.get("file_1");
    expect(file.contentType).toBe("text/plain");
    expect(client.baseUrl).toBe("http://example.test/v1");
    expect(fetchMock.mock.calls[0]?.[0].toString()).toBe("http://example.test/v1/files/file_1");
  });

  it("maps error envelopes", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json(
        { success: false, error: { code: "FILE_NOT_FOUND", message: "missing" } },
        { status: 404 },
      ),
    );
    const client = new UnifilesClient({ apiKey: "sk_test", fetch: fetchMock, maxRetries: 0 });
    await expect(client.files.get("missing")).rejects.toBeInstanceOf(NotFoundError);
  });

  it("converts nested public configuration to and from snake_case", async () => {
    let requestBody: Record<string, unknown> = {};
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (_input, init) => {
      requestBody = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return envelope(
        {
          id: "kb_1",
          name: "demo",
          chunking_strategy: { type: "semantic", chunk_size: 256, overlap: 20 },
          document_count: 0,
          chunk_count: 0,
          metadata: {},
          created_at: now,
        },
        201,
      );
    });
    const client = new UnifilesClient({ apiKey: "sk_test", fetch: fetchMock, maxRetries: 0 });
    const kb = await client.knowledgeBases.create("demo", {
      chunkingStrategy: { type: "semantic", chunkSize: 256, overlap: 20 },
    });
    const wireStrategy = requestBody.chunking_strategy as Record<string, unknown>;
    expect(wireStrategy.chunk_size).toBe(256);
    expect(wireStrategy.chunkSize).toBeUndefined();
    expect(kb.chunkingStrategy.chunkSize).toBe(256);
    expect(kb.chunkingStrategy.chunk_size).toBeUndefined();
  });

  it("waits for an extraction and updates the same object", async () => {
    const statuses = ["pending", "processing", "completed"];
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (_input, init) => {
      const status = init?.method === "POST" ? "pending" : statuses.shift() ?? "completed";
      return envelope(
        {
          id: "ext_1",
          file_id: "file_1",
          status,
          mode: "normal",
          markdown: status === "completed" ? "# Done" : null,
          created_at: now,
        },
        init?.method === "POST" ? 202 : 200,
      );
    });
    const client = new UnifilesClient({ apiKey: "sk_test", fetch: fetchMock, maxRetries: 0 });
    const extraction = await client.extractions.create("file_1");
    const result = await extraction.wait({ timeoutMs: 1_000, pollIntervalMs: 0 });
    expect(result).toBe(extraction);
    expect(extraction.markdown).toBe("# Done");
  });

  it("retries reads but not non-idempotent updates", async () => {
    const attempts = { GET: 0, PATCH: 0 };
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (_input, init) => {
      const method = String(init?.method ?? "GET") as keyof typeof attempts;
      attempts[method] += 1;
      if (method === "GET" && attempts.GET > 1) {
        return envelope({ items: [], total: 0, limit: 50, offset: 0, has_more: false });
      }
      return Response.json(
        { success: false, error: { code: "UNAVAILABLE", message: "retry" } },
        { status: 503 },
      );
    });
    const client = new UnifilesClient({
      apiKey: "sk_test",
      fetch: fetchMock,
      maxRetries: 1,
    });
    expect((await client.files.list()).items).toEqual([]);
    expect(attempts.GET).toBe(2);
    await expect(client.knowledgeBases.update("kb_1", { name: "new" })).rejects.toBeInstanceOf(
      ServerError,
    );
    expect(attempts.PATCH).toBe(1);
  });
});
