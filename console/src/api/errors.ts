/**
 * Structured API error with status code, error code, and detail message.
 * Replaces the generic `Error` thrown by `request.ts` so callers can
 * branch on status/code without parsing a string.
 */
export class ApiError extends Error {
  /** HTTP status code (e.g. 401, 403, 404, 500). */
  readonly status: number;
  /** Machine-readable error code from the backend (e.g. "MODEL_AUTH_FAILED"). */
  readonly code: string;
  /** Human-readable detail from the backend response body. */
  readonly detail: string;
  /** Raw response body payload, if available. */
  readonly payload: unknown;

  constructor(opts: {
    status: number;
    statusText: string;
    code?: string;
    detail?: string;
    payload?: unknown;
  }) {
    const detail = opts.detail || opts.statusText || "Unknown error";
    super(`[${opts.status}] ${detail}`);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code || "";
    this.detail = detail;
    this.payload = opts.payload ?? null;
  }

  /** True for 401 Unauthorized. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** True for 403 Forbidden. */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** True for 404 Not Found. */
  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** True for 5xx server errors. */
  get isServerError(): boolean {
    return this.status >= 500 && this.status < 600;
  }

  /** True for network-level failures (status 0). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /** True when the request is retryable (network error or 5xx). */
  get isRetryable(): boolean {
    return this.isNetworkError || this.isServerError;
  }
}

/**
 * Wrap a native fetch error (e.g. TypeError: Failed to fetch) into an ApiError
 * with status 0 so callers can handle it uniformly.
 */
export function wrapNetworkError(error: unknown): ApiError {
  const message =
    error instanceof Error ? error.message : "Network request failed";
  return new ApiError({
    status: 0,
    statusText: "Network Error",
    detail: message,
  });
}

/** Type guard for ApiError. */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
