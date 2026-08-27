import type { APIKeyResource } from "../generated/src/models/APIKeyResource.js";
import type { ChunkResource } from "../generated/src/models/ChunkResource.js";
import type { ChunkingStrategy as GeneratedChunkingStrategy } from "../generated/src/models/ChunkingStrategy.js";
import type { DeletionResult as GeneratedDeletionResult } from "../generated/src/models/DeletionResult.js";
import type { DocumentResource } from "../generated/src/models/DocumentResource.js";
import type { ExtractionOptions as GeneratedExtractionOptions } from "../generated/src/models/ExtractionOptions.js";
import type { ExtractionResource } from "../generated/src/models/ExtractionResource.js";
import type { FileList } from "../generated/src/models/FileList.js";
import type { FileResource as GeneratedFileResource } from "../generated/src/models/FileResource.js";
import type { KnowledgeBaseResource } from "../generated/src/models/KnowledgeBaseResource.js";
import type { SearchResults as GeneratedSearchResults } from "../generated/src/models/SearchResults.js";
import type { SupportedFileTypes as GeneratedSupportedFileTypes } from "../generated/src/models/SupportedFileTypes.js";
import type { UsageLimits as GeneratedUsageLimits } from "../generated/src/models/UsageLimits.js";
import type { UsageStats as GeneratedUsageStats } from "../generated/src/models/UsageStats.js";
import type { WebhookResource } from "../generated/src/models/WebhookResource.js";

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
