import { ProcessingError, TimeoutError } from "./errors.js";

export interface ListResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export interface FileResource {
  id: string;
  filename: string;
  contentType: string;
  size: number;
  metadata: Record<string, unknown>;
  tags: string[];
  createdAt: string;
  updatedAt?: string;
}

export interface ExtractionData {
  id: string;
  fileId: string;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  mode: string;
  progress?: number;
  markdown?: string;
  totalPages?: number;
  metadata?: Record<string, unknown>;
  error?: Record<string, unknown>;
  createdAt: string;
  completedAt?: string;
}

export class Extraction implements ExtractionData {
  id: string;
  fileId: string;
  status: ExtractionData["status"];
  mode: string;
  progress?: number;
  markdown?: string;
  totalPages?: number;
  metadata?: Record<string, unknown>;
  error?: Record<string, unknown>;
  createdAt: string;
  completedAt?: string;
  readonly #waiter: (id: string, options: WaitOptions) => Promise<Extraction>;

  constructor(data: ExtractionData, waiter: (id: string, options: WaitOptions) => Promise<Extraction>) {
    Object.assign(this, data);
    this.id = data.id;
    this.fileId = data.fileId;
    this.status = data.status;
    this.mode = data.mode;
    this.createdAt = data.createdAt;
    this.#waiter = waiter;
  }

  async wait(options: WaitOptions = {}): Promise<this> {
    const updated = await this.#waiter(this.id, options);
    Object.assign(this, updated);
    return this;
  }
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description?: string;
  chunkingStrategy: ChunkingStrategy;
  documentCount: number;
  chunkCount: number;
  metadata?: Record<string, unknown>;
  createdAt: string;
  updatedAt?: string;
}

export interface ChunkingStrategy {
  type: "fixed" | "semantic" | "hierarchical" | "paragraph";
  chunkSize: number;
  overlap: number;
  [key: string]: unknown;
}

export interface ExtractionOptions {
  language?: string;
  ocrProvider?: string;
  extractTables?: boolean;
  extractImages?: boolean;
  preserveLayout?: boolean;
  [key: string]: unknown;
}

export interface DocumentData {
  id: string;
  kbId: string;
  fileId: string;
  title?: string;
  status: "pending" | "indexing" | "indexed" | "failed" | "cancelled";
  chunkCount: number;
  metadata?: Record<string, unknown>;
  error?: Record<string, unknown>;
  createdAt: string;
  indexedAt?: string;
}

export class Document implements DocumentData {
  id: string;
  kbId: string;
  fileId: string;
  title?: string;
  status: DocumentData["status"];
  chunkCount: number;
  metadata?: Record<string, unknown>;
  error?: Record<string, unknown>;
  createdAt: string;
  indexedAt?: string;
  readonly #waiter: (kbId: string, id: string, options: WaitOptions) => Promise<Document>;

  constructor(
    data: DocumentData,
    waiter: (kbId: string, id: string, options: WaitOptions) => Promise<Document>,
  ) {
    Object.assign(this, data);
    this.id = data.id;
    this.kbId = data.kbId;
    this.fileId = data.fileId;
    this.status = data.status;
    this.chunkCount = data.chunkCount;
    this.createdAt = data.createdAt;
    this.#waiter = waiter;
  }

  async wait(options: WaitOptions = {}): Promise<this> {
    const updated = await this.#waiter(this.kbId, this.id, options);
    Object.assign(this, updated);
    return this;
  }
}

export interface Chunk {
  id: string;
  documentId: string;
  documentTitle?: string;
  content: string;
  score: number;
  vectorScore?: number;
  keywordScore?: number;
  metadata: Record<string, unknown>;
}

export interface SearchResults {
  query: string;
  chunks: Chunk[];
  total: number;
}

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  enabled: boolean;
  description?: string;
  lastDeliveryAt?: string;
  createdAt: string;
  updatedAt?: string;
}

export interface APIKey {
  id: string;
  name: string;
  key?: string;
  keyPrefix: string;
  scopes: string[];
  lastUsedAt?: string;
  expiresAt?: string;
  createdAt: string;
}

export interface UsageStats {
  storage: { usedBytes: number; limitBytes: number; usedPercentage: number };
  extraction: { pagesUsed: number; pagesLimit: number; resetAt?: string };
  knowledgeBases: { used: number; limit: number };
}

export interface UsageLimits {
  apiCalls: Record<string, unknown>;
  storage: Record<string, unknown>;
  files: Record<string, unknown>;
}

export interface DeletionResult {
  id: string;
  deleted: boolean;
}

export interface SupportedFileTypes {
  documentTypes: string[];
  imageTypes: string[];
  allTypes: string[];
}

export interface WaitOptions {
  timeoutMs?: number;
  pollIntervalMs?: number;
}

export function terminalFailure(data: ExtractionData | DocumentData): void {
  if (data.status === "failed" || data.status === "cancelled") {
    throw new ProcessingError(String(data.error?.message ?? "Processing failed"), {
      code: String(data.error?.code ?? "PROCESSING_FAILED"),
      details: data.error,
    });
  }
}

export function waitTimeout(kind: string, id: string, timeoutMs: number): never {
  throw new TimeoutError(`Timed out waiting for ${kind} ${id} after ${timeoutMs}ms`, {
    code: "WAIT_TIMEOUT",
  });
}
