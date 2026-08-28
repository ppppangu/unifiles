import type {
  APIKeyResource,
  ChunkResource,
  ChunkingStrategy as GeneratedChunkingStrategy,
  DeletionResult as GeneratedDeletionResult,
  DocumentResource,
  ExtractionOptions as GeneratedExtractionOptions,
  ExtractionResource,
  FileList,
  FileResource as GeneratedFileResource,
  KnowledgeBaseResource,
  SearchResults as GeneratedSearchResults,
  SupportedFileTypes as GeneratedSupportedFileTypes,
  UsageLimits as GeneratedUsageLimits,
  UsageStats as GeneratedUsageStats,
  WebhookResource,
} from "@wyy/unifiles-generated";

import { ProcessingError, TimeoutError } from "./errors.js";

export type FileResource = GeneratedFileResource;
export type KnowledgeBase = Omit<KnowledgeBaseResource, "chunkingStrategy"> & {
  chunkingStrategy: ChunkingStrategy;
};
export type Chunk = ChunkResource;
export type SearchResults = GeneratedSearchResults;
export type Webhook = WebhookResource;
export type APIKey = APIKeyResource;
export type UsageStats = GeneratedUsageStats;
export type UsageLimits = GeneratedUsageLimits;
export type DeletionResult = GeneratedDeletionResult;
export type SupportedFileTypes = GeneratedSupportedFileTypes;
export type ChunkingStrategy = GeneratedChunkingStrategy & {
  readonly chunk_size?: undefined;
};
export type ExtractionOptions = GeneratedExtractionOptions;
export type ExtractionData = ExtractionResource;
export type DocumentData = DocumentResource;

export type ListResponse<T> = Omit<FileList, "items"> & { items: T[] };

export interface WaitOptions {
  timeoutMs?: number;
  pollIntervalMs?: number;
}

export interface Extraction extends ExtractionResource {}
export class Extraction {
  readonly #waiter: (id: string, options: WaitOptions) => Promise<Extraction>;

  constructor(data: ExtractionResource, waiter: (id: string, options: WaitOptions) => Promise<Extraction>) {
    Object.assign(this, data);
    this.#waiter = waiter;
  }

  async wait(options: WaitOptions = {}): Promise<this> {
    const updated = await this.#waiter(this.id, options);
    Object.assign(this, updated);
    return this;
  }
}

export interface Document extends DocumentResource {}
export class Document {
  readonly #waiter: (kbId: string, id: string, options: WaitOptions) => Promise<Document>;

  constructor(
    data: DocumentResource,
    waiter: (kbId: string, id: string, options: WaitOptions) => Promise<Document>,
  ) {
    Object.assign(this, data);
    this.#waiter = waiter;
  }

  async wait(options: WaitOptions = {}): Promise<this> {
    const updated = await this.#waiter(this.kbId, this.id, options);
    Object.assign(this, updated);
    return this;
  }
}

export function terminalFailure(data: ExtractionResource | DocumentResource): void {
  if (data.status === "failed" || data.status === "cancelled") {
    const details = data.error ?? undefined;
    throw new ProcessingError(String(data.error?.message ?? "Processing failed"), {
      code: String(data.error?.code ?? "PROCESSING_FAILED"),
      ...(details ? { details } : {}),
    });
  }
}

export function waitTimeout(kind: string, id: string, timeoutMs: number): never {
  throw new TimeoutError(`Timed out waiting for ${kind} ${id} after ${timeoutMs}ms`, {
    code: "WAIT_TIMEOUT",
  });
}
