import {
  APIKeysApi,
  Configuration,
  DocumentsApi,
  ExtractionsApi,
  FilesApi,
  KnowledgeBasesApi,
  SearchApi,
  SystemApi,
  UsageApi,
  WebhooksApi,
  type Middleware,
} from "@wyy/unifiles-generated";

import {
  AuthenticationError,
  ConflictError,
  NotFoundError,
  PermissionError,
  RateLimitError,
  ServerError,
  TimeoutError,
  TransportError,
  UnifilesError,
  ValidationError,
} from "./errors.js";

export interface TransportOptions {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
  fetch?: typeof globalThis.fetch;
}

export interface GeneratedAPIs {
  files: FilesApi;
  extractions: ExtractionsApi;
  knowledgeBases: KnowledgeBasesApi;
  documents: DocumentsApi;
  search: SearchApi;
  webhooks: WebhooksApi;
  apiKeys: APIKeysApi;
  usage: UsageApi;
  system: SystemApi;
}

const retryableStatuses = new Set([408, 429, 500, 502, 503, 504]);
const sleep = async (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

const normalizeBaseUrl = (value: string | undefined): string => {
  const configured = (value ?? process.env.UNIFILES_BASE_URL ?? "https://api.unifiles.dev/v1").replace(
    /\/$/,
    "",
  );
  return configured.endsWith("/v1") ? configured : `${configured}/v1`;
};

const retryAfter = (response: Response): number | undefined => {
  const value = response.headers.get("retry-after");
  if (!value || !Number.isFinite(Number(value))) return undefined;
  return Math.max(0, Number(value) * 1_000);
};

const backoff = (attempt: number, response?: Response): number =>
  (response ? retryAfter(response) : undefined) ?? Math.random() * Math.min(8_000, 500 * 2 ** attempt);

const throwResponseError = async (response: Response): Promise<never> => {
  let body:
    | {
        error?: {
          code?: string;
          message?: string;
          details?: Record<string, unknown>;
          request_id?: string;
          retry_after?: number;
        };
      }
    | undefined;
  try {
    body = (await response.json()) as typeof body;
  } catch {
    body = undefined;
  }
  const wire = body?.error;
  const options = {
    code: wire?.code ?? `HTTP_${response.status}`,
    statusCode: response.status,
    ...((wire?.request_id ?? response.headers.get("x-request-id"))
      ? { requestId: wire?.request_id ?? response.headers.get("x-request-id") ?? undefined }
      : {}),
    ...(wire?.details ? { details: wire.details } : {}),
    ...(wire?.retry_after !== undefined ? { retryAfter: wire.retry_after } : {}),
  };
  const message = wire?.message ?? response.statusText ?? "Request failed";
  if (response.status === 401) throw new AuthenticationError(message, options);
  if (response.status === 403) throw new PermissionError(message, options);
  if (response.status === 404) throw new NotFoundError(message, options);
  if ([400, 413, 415, 422].includes(response.status)) throw new ValidationError(message, options);
  if (response.status === 409) throw new ConflictError(message, options);
  if (response.status === 429) throw new RateLimitError(message, options);
  if ([408, 504].includes(response.status)) throw new TimeoutError(message, options);
  if (response.status >= 500) throw new ServerError(message, options);
  throw new UnifilesError(message, options);
};

export class Transport {
  readonly baseUrl: string;
  readonly apis: GeneratedAPIs;

  constructor(options: TransportOptions = {}) {
    const apiKey = options.apiKey ?? process.env.UNIFILES_API_KEY;
    if (!apiKey) {
      throw new ValidationError("apiKey is required or set UNIFILES_API_KEY", {
        code: "MISSING_API_KEY",
      });
    }
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    const timeoutMs = options.timeoutMs ?? 30_000;
    const maxRetries = Math.max(0, options.maxRetries ?? 3);
    const baseFetch = options.fetch ?? globalThis.fetch;

    const fetchWithPolicy: typeof globalThis.fetch = async (input, init = {}) => {
      const method = String(init.method ?? "GET").toUpperCase();
      const headers = new Headers(init.headers);
      const retryAllowed = ["GET", "HEAD", "OPTIONS", "DELETE"].includes(method) ||
        headers.has("Idempotency-Key");
      for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
        try {
          const response = await baseFetch(input, {
            ...init,
            signal: AbortSignal.timeout(timeoutMs),
          });
          if (retryAllowed && retryableStatuses.has(response.status) && attempt < maxRetries) {
            await response.body?.cancel();
            await sleep(backoff(attempt, response));
            continue;
          }
          return response;
        } catch (error) {
          if (retryAllowed && attempt < maxRetries) {
            await sleep(backoff(attempt));
            continue;
          }
          if (error instanceof DOMException && error.name === "TimeoutError") {
            throw new TimeoutError(error.message, { code: "REQUEST_TIMEOUT", cause: error });
          }
          throw new TransportError(String(error), { code: "TRANSPORT_ERROR", cause: error });
        }
      }
      throw new TransportError("Request failed without a response", { code: "TRANSPORT_ERROR" });
    };

    const errorMiddleware: Middleware = {
      post: async ({ response }) => {
        if (!response.ok) await throwResponseError(response);
      },
    };
    const configuration = new Configuration({
      basePath: this.baseUrl.replace(/\/v1$/, ""),
      accessToken: apiKey,
      fetchApi: fetchWithPolicy,
      middleware: [errorMiddleware],
    });
    this.apis = {
      files: new FilesApi(configuration),
      extractions: new ExtractionsApi(configuration),
      knowledgeBases: new KnowledgeBasesApi(configuration),
      documents: new DocumentsApi(configuration),
      search: new SearchApi(configuration),
      webhooks: new WebhooksApi(configuration),
      apiKeys: new APIKeysApi(configuration),
      usage: new UsageApi(configuration),
      system: new SystemApi(configuration),
    };
  }
}
