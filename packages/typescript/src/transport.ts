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

interface SuccessEnvelope<T> {
  success: true;
  data: T;
}

interface ErrorEnvelope {
  success: false;
  error: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
    request_id?: string;
    retry_after?: number;
  };
}

export interface TransportOptions {
  apiKey?: string;
  baseUrl?: string;
  timeoutMs?: number;
  maxRetries?: number;
  fetch?: typeof globalThis.fetch;
}

export interface RequestOptions {
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  form?: FormData;
  idempotencyKey?: string;
}

const retryableStatuses = new Set([408, 429, 500, 502, 503, 504]);

const sleep = async (milliseconds: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

export class Transport {
  readonly baseUrl: string;
  readonly #apiKey: string;
  readonly #timeoutMs: number;
  readonly #maxRetries: number;
  readonly #fetch: typeof globalThis.fetch;

  constructor(options: TransportOptions = {}) {
    const apiKey = options.apiKey ?? process.env.UNIFILES_API_KEY;
    if (!apiKey) {
      throw new ValidationError("apiKey is required or set UNIFILES_API_KEY", {
        code: "MISSING_API_KEY",
      });
    }
    const configured = (options.baseUrl ?? process.env.UNIFILES_BASE_URL ?? "https://api.unifiles.dev/v1").replace(/\/$/, "");
    this.baseUrl = configured.endsWith("/v1") ? configured : `${configured}/v1`;
    this.#apiKey = apiKey;
    this.#timeoutMs = options.timeoutMs ?? 30_000;
    this.#maxRetries = Math.max(0, options.maxRetries ?? 3);
    this.#fetch = options.fetch ?? globalThis.fetch;
  }

  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const url = new URL(`${this.baseUrl}/${path.replace(/^\//, "")}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }

    const retryAllowed = ["GET", "HEAD", "OPTIONS", "DELETE"].includes(method.toUpperCase()) || Boolean(options.idempotencyKey);
    let response: Response | undefined;
    for (let attempt = 0; attempt <= this.#maxRetries; attempt += 1) {
      const headers = new Headers({
        Authorization: `Bearer ${this.#apiKey}`,
        Accept: "application/json",
        "User-Agent": "unifiles-node/0.1.0",
      });
      if (options.idempotencyKey) headers.set("Idempotency-Key", options.idempotencyKey);
      let body: BodyInit | undefined;
      if (options.form) {
        body = options.form;
      } else if (options.body !== undefined) {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(options.body);
      }

      try {
        const init: RequestInit = {
          method,
          headers,
          signal: AbortSignal.timeout(this.#timeoutMs),
        };
        if (body !== undefined) init.body = body;
        response = await this.#fetch(url, init);
      } catch (error) {
        if (retryAllowed && attempt < this.#maxRetries) {
          await sleep(this.#backoff(attempt));
          continue;
        }
        if (error instanceof DOMException && error.name === "TimeoutError") {
          throw new TimeoutError(error.message, { code: "REQUEST_TIMEOUT", cause: error });
        }
        throw new TransportError(String(error), { code: "TRANSPORT_ERROR", cause: error });
      }

      if (retryAllowed && retryableStatuses.has(response.status) && attempt < this.#maxRetries) {
        await sleep(this.#backoff(attempt, response));
        continue;
      }
      return this.#unwrap<T>(response);
    }
    throw new TransportError("Request failed without a response", { code: "TRANSPORT_ERROR" });
  }

  async binary(path: string): Promise<Uint8Array> {
    const response = await this.#fetch(`${this.baseUrl}/${path.replace(/^\//, "")}`, {
      headers: {
        Authorization: `Bearer ${this.#apiKey}`,
        Accept: "application/octet-stream",
        "User-Agent": "unifiles-node/0.1.0",
      },
      signal: AbortSignal.timeout(this.#timeoutMs),
    });
    if (!response.ok) await this.#throwResponseError(response);
    return new Uint8Array(await response.arrayBuffer());
  }

  #backoff(attempt: number, response?: Response): number {
    const retryAfter = response?.headers.get("retry-after");
    if (retryAfter && Number.isFinite(Number(retryAfter))) return Number(retryAfter) * 1000;
    return Math.random() * Math.min(8_000, 500 * 2 ** attempt);
  }

  async #unwrap<T>(response: Response): Promise<T> {
    if (!response.ok) await this.#throwResponseError(response);
    let envelope: SuccessEnvelope<T> | ErrorEnvelope;
    try {
      envelope = (await response.json()) as SuccessEnvelope<T> | ErrorEnvelope;
    } catch (error) {
      throw new TransportError("The API returned invalid JSON", {
        code: "INVALID_RESPONSE",
        statusCode: response.status,
        requestId: response.headers.get("x-request-id") ?? undefined,
        cause: error,
      });
    }
    if (!envelope.success || !("data" in envelope)) {
      throw new TransportError("The API returned an invalid success envelope", {
        code: "INVALID_RESPONSE",
        statusCode: response.status,
      });
    }
    return envelope.data;
  }

  async #throwResponseError(response: Response): Promise<never> {
    let body: ErrorEnvelope | undefined;
    try {
      body = (await response.json()) as ErrorEnvelope;
    } catch {
      body = undefined;
    }
    const wire = body?.error;
    const options = {
      code: wire?.code ?? `HTTP_${response.status}`,
      statusCode: response.status,
      requestId: wire?.request_id ?? response.headers.get("x-request-id") ?? undefined,
      details: wire?.details,
      retryAfter: wire?.retry_after,
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
  }
}
