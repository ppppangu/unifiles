export interface UnifilesErrorOptions {
  code?: string;
  statusCode?: number | undefined;
  requestId?: string | undefined;
  details?: Record<string, unknown> | undefined;
  retryAfter?: number | undefined;
  cause?: unknown;
}

export class UnifilesError extends Error {
  readonly code: string;
  readonly statusCode: number | undefined;
  readonly requestId: string | undefined;
  readonly details: Record<string, unknown>;

  constructor(message: string, options: UnifilesErrorOptions = {}) {
    super(message, { cause: options.cause });
    this.name = new.target.name;
    this.code = options.code ?? "UNIFILES_ERROR";
    this.statusCode = options.statusCode;
    this.requestId = options.requestId;
    this.details = options.details ?? {};
  }
}

export class AuthenticationError extends UnifilesError {}
export class PermissionError extends UnifilesError {}
export class NotFoundError extends UnifilesError {}
export class ValidationError extends UnifilesError {}
export class ConflictError extends UnifilesError {}
export class ProcessingError extends UnifilesError {}
export class ServerError extends UnifilesError {}
export class TimeoutError extends UnifilesError {}
export class TransportError extends UnifilesError {}

export class RateLimitError extends UnifilesError {
  readonly retryAfter: number | undefined;

  constructor(message: string, options: UnifilesErrorOptions = {}) {
    super(message, options);
    this.retryAfter = options.retryAfter;
  }
}
