import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";

import type {
  APIKeyCreate,
  ExtractionCreate as GeneratedExtractionCreate,
  WebhookCreate,
  WebhookUpdate,
} from "@wyy/unifiles-generated";

import { Transport } from "./transport.js";
import {
  type APIKey,
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

export interface UploadOptions {
  filename?: string;
  contentType?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

const chunking = (value: Partial<ChunkingStrategy> | undefined): ChunkingStrategy | undefined =>
  value
    ? {
        type: value.type ?? "semantic",
        chunkSize: value.chunkSize ?? 512,
        overlap: value.overlap ?? 50,
      }
    : undefined;

export class FilesResource {
  constructor(private readonly transport: Transport) {}

  async upload(input: string | Uint8Array, options: UploadOptions = {}): Promise<FileResource> {
    const content = typeof input === "string" ? await readFile(input) : input;
    const filename = options.filename ?? (typeof input === "string" ? basename(input) : undefined);
    if (!filename) throw new TypeError("filename is required when uploading bytes");
    const bytes = Uint8Array.from(content);
    const file = new File([bytes.buffer], filename, {
      type: options.contentType ?? "application/octet-stream",
    });
    const response = await this.transport.apis.files.uploadFile({
      file,
      idempotencyKey: randomUUID(),
      metadata: JSON.stringify(options.metadata ?? {}),
      tags: JSON.stringify(options.tags ?? []),
    });
    return response.data;
  }

  async list(options: {
    limit?: number;
    offset?: number;
    tags?: string[];
    contentType?: string;
    sortBy?: string;
    order?: "asc" | "desc";
  } = {}): Promise<ListResponse<FileResource>> {
    const response = await this.transport.apis.files.listFiles({
      limit: options.limit ?? 50,
      offset: options.offset ?? 0,
      ...(options.tags ? { tags: options.tags.join(",") } : {}),
      ...(options.contentType ? { contentType: options.contentType } : {}),
      sortBy: options.sortBy ?? "created_at",
      order: options.order ?? "desc",
    });
    return response.data;
  }

  async get(fileId: string): Promise<FileResource> {
    return (await this.transport.apis.files.getFile({ fileId })).data;
  }

  async download(fileId: string): Promise<Uint8Array> {
    const blob = await this.transport.apis.files.downloadFile({ fileId });
    return new Uint8Array(await blob.arrayBuffer());
  }

  async delete(fileId: string): Promise<DeletionResult> {
    return (await this.transport.apis.files.deleteFile({ fileId })).data;
  }

  async listSupportedTypes(): Promise<SupportedFileTypes> {
    return (await this.transport.apis.files.listSupportedFileTypes()).data;
  }
}

export class ExtractionsResource {
  constructor(private readonly transport: Transport) {}

  #bind = (data: ExtractionData): Extraction => new Extraction(data, this.#wait);

  async create(
    fileId: string,
    options: { mode?: string; options?: ExtractionOptions } = {},
  ): Promise<Extraction> {
    const response = await this.transport.apis.extractions.createExtraction({
      extractionCreate: {
        fileId,
        mode: (options.mode ?? "normal") as NonNullable<GeneratedExtractionCreate["mode"]>,
        ...(options.options ? { options: options.options } : {}),
      },
      idempotencyKey: randomUUID(),
    });
    return this.#bind(response.data);
  }

  async get(extractionId: string): Promise<Extraction> {
    return this.#bind((await this.transport.apis.extractions.getExtraction({ extractionId })).data);
  }

  async list(
    fileId: string,
    options: { limit?: number; offset?: number } = {},
  ): Promise<ListResponse<Extraction>> {
    const response = await this.transport.apis.extractions.listFileExtractions({
      fileId,
      limit: options.limit ?? 50,
      offset: options.offset ?? 0,
    });
    return { ...response.data, items: response.data.items.map(this.#bind) };
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

  #bind = (data: DocumentData): Document => new Document(data, this.#wait);

  async create(
    kbId: string,
    fileId: string,
    options: { title?: string; metadata?: Record<string, unknown> } = {},
  ): Promise<Document> {
    const response = await this.transport.apis.documents.createDocument({
      kbId,
      documentCreate: {
        fileId,
        ...(options.title !== undefined ? { title: options.title } : {}),
        ...(options.metadata ? { metadata: options.metadata } : {}),
      },
      idempotencyKey: randomUUID(),
    });
    return this.#bind(response.data);
  }

  async list(
    kbId: string,
    options: { limit?: number; offset?: number } = {},
  ): Promise<ListResponse<Document>> {
    const response = await this.transport.apis.documents.listDocuments({
      kbId,
      limit: options.limit ?? 50,
      offset: options.offset ?? 0,
    });
    return { ...response.data, items: response.data.items.map(this.#bind) };
  }

  async get(kbId: string, documentId: string): Promise<Document> {
    return this.#bind(
      (await this.transport.apis.documents.getDocument({ kbId, documentId })).data,
    );
  }

  async delete(kbId: string, documentId: string): Promise<DeletionResult> {
    return (await this.transport.apis.documents.deleteDocument({ kbId, documentId })).data;
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
    options: {
      description?: string;
      chunkingStrategy?: Partial<ChunkingStrategy>;
      metadata?: Record<string, unknown>;
    } = {},
  ): Promise<KnowledgeBase> {
    const response = await this.transport.apis.knowledgeBases.createKnowledgeBase({
      knowledgeBaseCreate: {
        name,
        ...(options.description !== undefined ? { description: options.description } : {}),
        ...(options.chunkingStrategy
          ? { chunkingStrategy: chunking(options.chunkingStrategy) as ChunkingStrategy }
          : {}),
        ...(options.metadata ? { metadata: options.metadata } : {}),
      },
      idempotencyKey: randomUUID(),
    });
    return response.data;
  }

  async list(options: { limit?: number; offset?: number } = {}): Promise<ListResponse<KnowledgeBase>> {
    return (
      await this.transport.apis.knowledgeBases.listKnowledgeBases({
        limit: options.limit ?? 50,
        offset: options.offset ?? 0,
      })
    ).data;
  }

  async get(kbId: string): Promise<KnowledgeBase> {
    return (await this.transport.apis.knowledgeBases.getKnowledgeBase({ kbId })).data;
  }

  async update(
    kbId: string,
    changes: {
      name?: string;
      description?: string;
      chunkingStrategy?: Partial<ChunkingStrategy>;
      metadata?: Record<string, unknown>;
    },
  ): Promise<KnowledgeBase> {
    return (
      await this.transport.apis.knowledgeBases.updateKnowledgeBase({
        kbId,
        knowledgeBaseUpdate: {
          ...(changes.name !== undefined ? { name: changes.name } : {}),
          ...(changes.description !== undefined ? { description: changes.description } : {}),
          ...(changes.chunkingStrategy
            ? { chunkingStrategy: chunking(changes.chunkingStrategy) as ChunkingStrategy }
            : {}),
          ...(changes.metadata ? { metadata: changes.metadata } : {}),
        },
      })
    ).data;
  }

  async delete(kbId: string): Promise<DeletionResult> {
    return (await this.transport.apis.knowledgeBases.deleteKnowledgeBase({ kbId })).data;
  }

  async search(
    kbId: string,
    query: string,
    options: { topK?: number; threshold?: number; filter?: Record<string, unknown> } = {},
  ): Promise<SearchResults> {
    return (
      await this.transport.apis.search.searchKnowledgeBase({
        kbId,
        searchRequest: {
          query,
          topK: options.topK ?? 5,
          threshold: options.threshold ?? 0,
          ...(options.filter ? { filter: options.filter } : {}),
        },
      })
    ).data;
  }

  async hybridSearch(
    kbId: string,
    query: string,
    options: { vectorWeight?: number; keywordWeight?: number; topK?: number } = {},
  ): Promise<SearchResults> {
    return (
      await this.transport.apis.search.hybridSearchKnowledgeBase({
        kbId,
        hybridSearchRequest: {
          query,
          vectorWeight: options.vectorWeight ?? 0.7,
          keywordWeight: options.keywordWeight ?? 0.3,
          topK: options.topK ?? 5,
        },
      })
    ).data;
  }
}

export class WebhooksResource {
  constructor(private readonly transport: Transport) {}

  async create(
    url: string,
    events: string[],
    options: { description?: string } = {},
  ): Promise<Webhook> {
    return (
      await this.transport.apis.webhooks.createWebhook({
        webhookCreate: {
          url,
          events: events as WebhookCreate["events"],
          ...(options.description !== undefined ? { description: options.description } : {}),
        },
        idempotencyKey: randomUUID(),
      })
    ).data;
  }

  async list(options: { limit?: number; offset?: number } = {}): Promise<ListResponse<Webhook>> {
    return (
      await this.transport.apis.webhooks.listWebhooks({
        limit: options.limit ?? 50,
        offset: options.offset ?? 0,
      })
    ).data;
  }

  async get(id: string): Promise<Webhook> {
    return (await this.transport.apis.webhooks.getWebhook({ webhookId: id })).data;
  }

  async update(
    id: string,
    changes: Partial<Pick<Webhook, "url" | "events" | "enabled" | "description">>,
  ): Promise<Webhook> {
    const { url, events, enabled, description } = changes;
    return (
      await this.transport.apis.webhooks.updateWebhook({
        webhookId: id,
        webhookUpdate: {
          ...(url !== undefined ? { url } : {}),
          ...(events !== undefined
            ? { events: events as NonNullable<WebhookUpdate["events"]> }
            : {}),
          ...(enabled !== undefined ? { enabled } : {}),
          ...(description !== undefined ? { description } : {}),
        },
      })
    ).data;
  }

  async delete(id: string): Promise<DeletionResult> {
    return (await this.transport.apis.webhooks.deleteWebhook({ webhookId: id })).data;
  }
}

export class APIKeysResource {
  constructor(private readonly transport: Transport) {}

  async create(
    name: string,
    options: { scopes?: string[]; expiresAt?: string } = {},
  ): Promise<APIKey> {
    return (
      await this.transport.apis.apiKeys.createApiKey({
        apiKeyCreate: {
          name,
          ...(options.scopes ? { scopes: options.scopes } : {}),
          ...(options.expiresAt ? { expiresAt: options.expiresAt } : {}),
        } satisfies APIKeyCreate,
        idempotencyKey: randomUUID(),
      })
    ).data;
  }

  async list(options: { limit?: number; offset?: number } = {}): Promise<ListResponse<APIKey>> {
    return (
      await this.transport.apis.apiKeys.listApiKeys({
        limit: options.limit ?? 50,
        offset: options.offset ?? 0,
      })
    ).data;
  }

  async delete(id: string): Promise<DeletionResult> {
    return (await this.transport.apis.apiKeys.revokeApiKey({ keyId: id })).data;
  }

  revoke(id: string): Promise<DeletionResult> {
    return this.delete(id);
  }
}

export class UsageResource {
  constructor(private readonly transport: Transport) {}

  async getStats(): Promise<UsageStats> {
    return (await this.transport.apis.usage.getUsageStats()).data;
  }

  async getLimits(): Promise<UsageLimits> {
    return (await this.transport.apis.usage.getUsageLimits()).data;
  }
}
