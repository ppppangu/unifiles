import { readFile } from "node:fs/promises";
import { basename } from "node:path";
import { randomUUID } from "node:crypto";

import { Transport } from "./transport.js";
import {
  type APIKey,
  type Chunk,
  type ChunkingStrategy,
  type DeletionResult,
  Document,
  type DocumentData,
  Extraction,
  type ExtractionData,
  type ExtractionOptions,
  type FileResource,
  type KnowledgeBase,
  type ListResponse,
  type SearchResults,
  type SupportedFileTypes,
  type UsageLimits,
  type UsageStats,
  type WaitOptions,
  type Webhook,
  terminalFailure,
  waitTimeout,
} from "./types.js";

type Wire = Record<string, unknown>;

const object = (value: unknown): Wire => (value && typeof value === "object" ? (value as Wire) : {});
const array = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const compact = (value: Wire): Wire =>
  Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined));

const listFromWire = <T>(wire: Wire, map: (item: Wire) => T): ListResponse<T> => ({
  items: array(wire.items).map((item) => map(object(item))),
  total: Number(wire.total ?? 0),
  limit: Number(wire.limit ?? 50),
  offset: Number(wire.offset ?? 0),
  hasMore: Boolean(wire.has_more),
});

const fileFromWire = (wire: Wire): FileResource => ({
  id: String(wire.id),
  filename: String(wire.filename),
  contentType: String(wire.content_type),
  size: Number(wire.size),
  metadata: object(wire.metadata),
  tags: array(wire.tags).map(String),
  createdAt: String(wire.created_at),
  ...(wire.updated_at ? { updatedAt: String(wire.updated_at) } : {}),
});

const extractionDataFromWire = (wire: Wire): ExtractionData => ({
  id: String(wire.id),
  fileId: String(wire.file_id),
  status: String(wire.status) as ExtractionData["status"],
  mode: String(wire.mode ?? "normal"),
  createdAt: String(wire.created_at),
  ...(wire.progress !== undefined ? { progress: Number(wire.progress) } : {}),
  ...(wire.markdown !== undefined && wire.markdown !== null ? { markdown: String(wire.markdown) } : {}),
  ...(wire.total_pages !== undefined && wire.total_pages !== null ? { totalPages: Number(wire.total_pages) } : {}),
  ...(wire.metadata ? { metadata: object(wire.metadata) } : {}),
  ...(wire.error ? { error: object(wire.error) } : {}),
  ...(wire.completed_at ? { completedAt: String(wire.completed_at) } : {}),
});

const kbFromWire = (wire: Wire): KnowledgeBase => ({
  id: String(wire.id),
  name: String(wire.name),
  chunkingStrategy: chunkingFromWire(object(wire.chunking_strategy)),
  documentCount: Number(wire.document_count ?? 0),
  chunkCount: Number(wire.chunk_count ?? 0),
  createdAt: String(wire.created_at),
  ...(wire.description !== undefined && wire.description !== null ? { description: String(wire.description) } : {}),
  ...(wire.metadata ? { metadata: object(wire.metadata) } : {}),
  ...(wire.updated_at ? { updatedAt: String(wire.updated_at) } : {}),
});

const chunkingFromWire = (wire: Wire): ChunkingStrategy => {
  const { chunk_size, ...rest } = wire;
  return {
    ...rest,
    type: String(wire.type ?? "semantic") as ChunkingStrategy["type"],
    chunkSize: Number(chunk_size ?? 512),
    overlap: Number(wire.overlap ?? 50),
  };
};

const chunkingToWire = (value: Partial<ChunkingStrategy> | undefined): Wire | undefined => {
  if (!value) return undefined;
  const { chunkSize, overlap, ...rest } = value;
  return compact({ ...rest, chunk_size: chunkSize, overlap });
};

const extractionOptionsToWire = (value: ExtractionOptions | undefined): Wire => {
  if (!value) return {};
  const { ocrProvider, extractTables, extractImages, preserveLayout, ...rest } = value;
  return compact({
    ...rest,
    ocr_provider: ocrProvider,
    extract_tables: extractTables,
    extract_images: extractImages,
    preserve_layout: preserveLayout,
  });
};

const documentDataFromWire = (wire: Wire): DocumentData => ({
  id: String(wire.id),
  kbId: String(wire.kb_id),
  fileId: String(wire.file_id),
  status: String(wire.status) as DocumentData["status"],
  chunkCount: Number(wire.chunk_count ?? 0),
  createdAt: String(wire.created_at),
  ...(wire.title !== undefined && wire.title !== null ? { title: String(wire.title) } : {}),
  ...(wire.metadata ? { metadata: object(wire.metadata) } : {}),
  ...(wire.error ? { error: object(wire.error) } : {}),
  ...(wire.indexed_at ? { indexedAt: String(wire.indexed_at) } : {}),
});

const chunkFromWire = (wire: Wire): Chunk => ({
  id: String(wire.id),
  documentId: String(wire.document_id),
  content: String(wire.content),
  score: Number(wire.score),
  metadata: object(wire.metadata),
  ...(wire.document_title ? { documentTitle: String(wire.document_title) } : {}),
  ...(wire.vector_score !== undefined ? { vectorScore: Number(wire.vector_score) } : {}),
  ...(wire.keyword_score !== undefined ? { keywordScore: Number(wire.keyword_score) } : {}),
});

const searchFromWire = (wire: Wire): SearchResults => ({
  query: String(wire.query),
  chunks: array(wire.chunks).map((item) => chunkFromWire(object(item))),
  total: Number(wire.total ?? 0),
});

const webhookFromWire = (wire: Wire): Webhook => ({
  id: String(wire.id),
  url: String(wire.url),
  events: array(wire.events).map(String),
  enabled: Boolean(wire.enabled ?? true),
  createdAt: String(wire.created_at),
  ...(wire.description ? { description: String(wire.description) } : {}),
  ...(wire.last_delivery_at ? { lastDeliveryAt: String(wire.last_delivery_at) } : {}),
  ...(wire.updated_at ? { updatedAt: String(wire.updated_at) } : {}),
});

const apiKeyFromWire = (wire: Wire): APIKey => ({
  id: String(wire.id),
  name: String(wire.name),
  keyPrefix: String(wire.key_prefix),
  scopes: array(wire.scopes).map(String),
  createdAt: String(wire.created_at),
  ...(wire.key ? { key: String(wire.key) } : {}),
  ...(wire.last_used_at ? { lastUsedAt: String(wire.last_used_at) } : {}),
  ...(wire.expires_at ? { expiresAt: String(wire.expires_at) } : {}),
});

const deletionFromWire = (wire: Wire): DeletionResult => ({
  id: String(wire.id),
  deleted: Boolean(wire.deleted),
});

export interface UploadOptions {
  filename?: string;
  contentType?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export class FilesResource {
  constructor(private readonly transport: Transport) {}

  async upload(input: string | Uint8Array, options: UploadOptions = {}): Promise<FileResource> {
    const content = typeof input === "string" ? await readFile(input) : input;
    const filename = options.filename ?? (typeof input === "string" ? basename(input) : undefined);
    if (!filename) throw new TypeError("filename is required when uploading bytes");
    const form = new FormData();
    const bytes = Uint8Array.from(content);
    const blob = options.contentType
      ? new Blob([bytes.buffer], { type: options.contentType })
      : new Blob([bytes.buffer]);
    form.set("file", blob, filename);
    form.set("metadata", JSON.stringify(options.metadata ?? {}));
    form.set("tags", JSON.stringify(options.tags ?? []));
    const wire = await this.transport.request<Wire>("POST", "files", {
      form,
      idempotencyKey: randomUUID(),
    });
    return fileFromWire(wire);
  }

  async list(options: {
    limit?: number;
    offset?: number;
    tags?: string[];
    contentType?: string;
    sortBy?: string;
    order?: "asc" | "desc";
  } = {}): Promise<ListResponse<FileResource>> {
    const wire = await this.transport.request<Wire>("GET", "files", {
      query: {
        limit: options.limit ?? 50,
        offset: options.offset ?? 0,
        tags: options.tags?.join(","),
        content_type: options.contentType,
        sort_by: options.sortBy ?? "created_at",
        order: options.order ?? "desc",
      },
    });
    return listFromWire(wire, fileFromWire);
  }

  async get(fileId: string): Promise<FileResource> {
    return fileFromWire(await this.transport.request<Wire>("GET", `files/${fileId}`));
  }

  download(fileId: string): Promise<Uint8Array> {
    return this.transport.binary(`files/${fileId}/download`);
  }

  async delete(fileId: string): Promise<DeletionResult> {
    return deletionFromWire(await this.transport.request<Wire>("DELETE", `files/${fileId}`));
  }

  async listSupportedTypes(): Promise<SupportedFileTypes> {
    const wire = await this.transport.request<Wire>("GET", "files/types");
    return {
      documentTypes: array(wire.document_types).map(String),
      imageTypes: array(wire.image_types).map(String),
      allTypes: array(wire.all_types).map(String),
    };
  }
}

export class ExtractionsResource {
  constructor(private readonly transport: Transport) {}

  #fromWire = (wire: Wire): Extraction => new Extraction(extractionDataFromWire(wire), this.#wait);

  async create(fileId: string, options: { mode?: string; options?: ExtractionOptions } = {}): Promise<Extraction> {
    const wire = await this.transport.request<Wire>("POST", "extractions", {
      body: {
        file_id: fileId,
        mode: options.mode ?? "normal",
        options: extractionOptionsToWire(options.options),
      },
      idempotencyKey: randomUUID(),
    });
    return this.#fromWire(wire);
  }

  async get(extractionId: string): Promise<Extraction> {
    return this.#fromWire(await this.transport.request<Wire>("GET", `extractions/${extractionId}`));
  }

  async list(fileId: string, options: { limit?: number; offset?: number } = {}): Promise<ListResponse<Extraction>> {
    const wire = await this.transport.request<Wire>("GET", `files/${fileId}/extractions`, {
      query: { limit: options.limit ?? 50, offset: options.offset ?? 0 },
    });
    return listFromWire(wire, this.#fromWire);
  }

  #wait = async (id: string, options: WaitOptions): Promise<Extraction> => {
    const timeoutMs = options.timeoutMs ?? 300_000;
    const pollIntervalMs = options.pollIntervalMs ?? 2_000;
    const deadline = Date.now() + timeoutMs;
    while (true) {
      const extraction = await this.get(id);
      terminalFailure(extraction);
      if (extraction.status === "completed") return extraction;
      if (Date.now() >= deadline) waitTimeout("extraction", id, timeoutMs);
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }
  };
}

export class DocumentsResource {
  constructor(private readonly transport: Transport) {}

  #fromWire = (wire: Wire): Document => new Document(documentDataFromWire(wire), this.#wait);

  async create(
    kbId: string,
    fileId: string,
    options: { title?: string; metadata?: Record<string, unknown> } = {},
  ): Promise<Document> {
    const wire = await this.transport.request<Wire>("POST", `knowledge-bases/${kbId}/documents`, {
      body: compact({ file_id: fileId, title: options.title, metadata: options.metadata }),
      idempotencyKey: randomUUID(),
    });
    return this.#fromWire(wire);
  }

  async list(kbId: string, options: { limit?: number; offset?: number } = {}): Promise<ListResponse<Document>> {
    const wire = await this.transport.request<Wire>("GET", `knowledge-bases/${kbId}/documents`, {
      query: { limit: options.limit ?? 50, offset: options.offset ?? 0 },
    });
    return listFromWire(wire, this.#fromWire);
  }

  async get(kbId: string, documentId: string): Promise<Document> {
    return this.#fromWire(
      await this.transport.request<Wire>("GET", `knowledge-bases/${kbId}/documents/${documentId}`),
    );
  }

  async delete(kbId: string, documentId: string): Promise<DeletionResult> {
    return deletionFromWire(
      await this.transport.request<Wire>("DELETE", `knowledge-bases/${kbId}/documents/${documentId}`),
    );
  }

  #wait = async (kbId: string, id: string, options: WaitOptions): Promise<Document> => {
    const timeoutMs = options.timeoutMs ?? 300_000;
    const pollIntervalMs = options.pollIntervalMs ?? 2_000;
    const deadline = Date.now() + timeoutMs;
    while (true) {
      const document = await this.get(kbId, id);
      terminalFailure(document);
      if (document.status === "indexed") return document;
      if (Date.now() >= deadline) waitTimeout("document", id, timeoutMs);
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }
  };
}

export class KnowledgeBasesResource {
  readonly documents: DocumentsResource;

  constructor(private readonly transport: Transport) {
    this.documents = new DocumentsResource(transport);
  }

  async create(
    name: string,
    options: { description?: string; chunkingStrategy?: Partial<ChunkingStrategy>; metadata?: Record<string, unknown> } = {},
  ): Promise<KnowledgeBase> {
    const wire = await this.transport.request<Wire>("POST", "knowledge-bases", {
      body: compact({
        name,
        description: options.description,
        chunking_strategy: chunkingToWire(options.chunkingStrategy),
        metadata: options.metadata,
      }),
      idempotencyKey: randomUUID(),
    });
    return kbFromWire(wire);
  }

  async list(options: { limit?: number; offset?: number } = {}): Promise<ListResponse<KnowledgeBase>> {
    const wire = await this.transport.request<Wire>("GET", "knowledge-bases", {
      query: { limit: options.limit ?? 50, offset: options.offset ?? 0 },
    });
    return listFromWire(wire, kbFromWire);
  }

  async get(kbId: string): Promise<KnowledgeBase> {
    return kbFromWire(await this.transport.request<Wire>("GET", `knowledge-bases/${kbId}`));
  }

  async update(
    kbId: string,
    changes: { name?: string; description?: string; chunkingStrategy?: Partial<ChunkingStrategy>; metadata?: Record<string, unknown> },
  ): Promise<KnowledgeBase> {
    const wire = await this.transport.request<Wire>("PATCH", `knowledge-bases/${kbId}`, {
      body: compact({
        name: changes.name,
        description: changes.description,
        chunking_strategy: chunkingToWire(changes.chunkingStrategy),
        metadata: changes.metadata,
      }),
    });
    return kbFromWire(wire);
  }

  async delete(kbId: string): Promise<DeletionResult> {
    return deletionFromWire(await this.transport.request<Wire>("DELETE", `knowledge-bases/${kbId}`));
  }

  async search(
    kbId: string,
    query: string,
    options: { topK?: number; threshold?: number; filter?: Record<string, unknown> } = {},
  ): Promise<SearchResults> {
    const wire = await this.transport.request<Wire>("POST", `knowledge-bases/${kbId}/search`, {
      body: compact({ query, top_k: options.topK ?? 5, threshold: options.threshold ?? 0, filter: options.filter }),
      idempotencyKey: randomUUID(),
    });
    return searchFromWire(wire);
  }

  async hybridSearch(
    kbId: string,
    query: string,
    options: { vectorWeight?: number; keywordWeight?: number; topK?: number } = {},
  ): Promise<SearchResults> {
    const wire = await this.transport.request<Wire>("POST", `knowledge-bases/${kbId}/hybrid-search`, {
      body: {
        query,
        vector_weight: options.vectorWeight ?? 0.7,
        keyword_weight: options.keywordWeight ?? 0.3,
        top_k: options.topK ?? 5,
      },
      idempotencyKey: randomUUID(),
    });
    return searchFromWire(wire);
  }
}

export class WebhooksResource {
  constructor(private readonly transport: Transport) {}

  async create(url: string, events: string[], options: { description?: string } = {}): Promise<Webhook> {
    const wire = await this.transport.request<Wire>("POST", "webhooks", {
      body: compact({ url, events, description: options.description }),
      idempotencyKey: randomUUID(),
    });
    return webhookFromWire(wire);
  }

  async list(options: { limit?: number; offset?: number } = {}): Promise<ListResponse<Webhook>> {
    const wire = await this.transport.request<Wire>("GET", "webhooks", {
      query: { limit: options.limit ?? 50, offset: options.offset ?? 0 },
    });
    return listFromWire(wire, webhookFromWire);
  }

  async get(id: string): Promise<Webhook> {
    return webhookFromWire(await this.transport.request<Wire>("GET", `webhooks/${id}`));
  }

  async update(id: string, changes: Partial<Pick<Webhook, "url" | "events" | "enabled" | "description">>): Promise<Webhook> {
    return webhookFromWire(await this.transport.request<Wire>("PATCH", `webhooks/${id}`, { body: changes }));
  }

  async delete(id: string): Promise<DeletionResult> {
    return deletionFromWire(await this.transport.request<Wire>("DELETE", `webhooks/${id}`));
  }
}

export class APIKeysResource {
  constructor(private readonly transport: Transport) {}

  async create(name: string, options: { scopes?: string[]; expiresAt?: string } = {}): Promise<APIKey> {
    const wire = await this.transport.request<Wire>("POST", "api-keys", {
      body: compact({ name, scopes: options.scopes, expires_at: options.expiresAt }),
      idempotencyKey: randomUUID(),
    });
    return apiKeyFromWire(wire);
  }

  async list(options: { limit?: number; offset?: number } = {}): Promise<ListResponse<APIKey>> {
    const wire = await this.transport.request<Wire>("GET", "api-keys", {
      query: { limit: options.limit ?? 50, offset: options.offset ?? 0 },
    });
    return listFromWire(wire, apiKeyFromWire);
  }

  async delete(id: string): Promise<DeletionResult> {
    return deletionFromWire(await this.transport.request<Wire>("DELETE", `api-keys/${id}`));
  }

  revoke(id: string): Promise<DeletionResult> {
    return this.delete(id);
  }
}

export class UsageResource {
  constructor(private readonly transport: Transport) {}

  async getStats(): Promise<UsageStats> {
    const wire = await this.transport.request<Wire>("GET", "usage/stats");
    const storage = object(wire.storage);
    const extraction = object(wire.extraction);
    const knowledgeBases = object(wire.knowledge_bases);
    return {
      storage: {
        usedBytes: Number(storage.used_bytes ?? 0),
        limitBytes: Number(storage.limit_bytes ?? 0),
        usedPercentage: Number(storage.used_percentage ?? 0),
      },
      extraction: {
        pagesUsed: Number(extraction.pages_used ?? 0),
        pagesLimit: Number(extraction.pages_limit ?? 0),
        ...(extraction.reset_at ? { resetAt: String(extraction.reset_at) } : {}),
      },
      knowledgeBases: {
        used: Number(knowledgeBases.used ?? 0),
        limit: Number(knowledgeBases.limit ?? 0),
      },
    };
  }

  async getLimits(): Promise<UsageLimits> {
    const wire = await this.transport.request<Wire>("GET", "usage/limits");
    return { apiCalls: object(wire.api_calls), storage: object(wire.storage), files: object(wire.files) };
  }
}
