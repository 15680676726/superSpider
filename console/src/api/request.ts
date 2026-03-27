import { getApiUrl, getApiToken } from "./config";
import { ApiError, wrapNetworkError } from "./errors";

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DEFAULT_MAX_RETRIES = 2;
const RETRY_BASE_DELAY_MS = 500;
const RETRY_MAX_DELAY_MS = 5_000;

// ---------------------------------------------------------------------------
// Global interceptor registry
// ---------------------------------------------------------------------------

export type ResponseInterceptor = (
  error: ApiError,
) => void | boolean | Promise<void | boolean>;

const responseInterceptors: ResponseInterceptor[] = [];

/**
 * Register a global response-error interceptor.
 * Return `true` from the interceptor to suppress the error (swallow it).
 * Returns an unsubscribe function.
 */
export function onResponseError(interceptor: ResponseInterceptor): () => void {
  responseInterceptors.push(interceptor);
  return () => {
    const idx = responseInterceptors.indexOf(interceptor);
    if (idx >= 0) responseInterceptors.splice(idx, 1);
  };
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function buildHeaders(method?: string, extra?: HeadersInit): Headers {
  const headers = extra instanceof Headers ? extra : new Headers(extra);

  if (method && ["POST", "PUT", "PATCH"].includes(method.toUpperCase())) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }

  const token = getApiToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}

/**
 * Build an auth-only Headers instance for raw fetch calls (file upload/download).
 * Exported so that `workspace.ts`, `system.ts` etc. can attach auth to direct
 * `fetch()` calls without duplicating the token logic.
 */
export function buildAuthHeaders(extra?: HeadersInit): Headers {
  const headers = extra instanceof Headers ? extra : new Headers(extra);
  const token = getApiToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return headers;
}

async function parseErrorPayload(
  response: Response,
): Promise<{ code: string; detail: string; payload: unknown }> {
  const contentType = response.headers.get("content-type") || "";
  let code = "";
  let detail = "";
  let payload: unknown = null;

  if (contentType.includes("application/json")) {
    const json = await response.json().catch(() => null);
    payload = json;
    if (json && typeof json === "object") {
      const obj = json as Record<string, unknown>;
      if (typeof obj.code === "string") code = obj.code;
      if (typeof obj.detail === "string") {
        detail = obj.detail;
      } else if (typeof obj.message === "string") {
        detail = obj.message;
      } else if (obj.detail !== undefined) {
        detail = JSON.stringify(obj.detail);
      } else {
        detail = JSON.stringify(json);
      }
    }
  }

  if (!detail) {
    detail = await response.text().catch(() => "");
  }

  return { code, detail, payload };
}

function retryDelay(attempt: number): number {
  // Exponential back-off with jitter, capped at RETRY_MAX_DELAY_MS
  const base = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
  const jitter = Math.random() * RETRY_BASE_DELAY_MS;
  return Math.min(base + jitter, RETRY_MAX_DELAY_MS);
}

function isRetryableMethod(method: string): boolean {
  const upper = method.toUpperCase();
  return upper === "GET" || upper === "HEAD" || upper === "OPTIONS";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function runInterceptors(error: ApiError): Promise<boolean> {
  for (const interceptor of responseInterceptors) {
    try {
      const result = await interceptor(error);
      if (result === true) return true; // suppressed
    } catch {
      // interceptor threw — ignore and continue
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Extended request options
// ---------------------------------------------------------------------------

export interface RequestOptions extends RequestInit {
  /** Max retry attempts for retryable errors. Set 0 to disable. Default: 2 */
  maxRetries?: number;
  /** Force retry even for non-idempotent methods (POST/PUT/PATCH). Default: false */
  forceRetry?: boolean;
  /** Skip global error interceptors for this request. Default: false */
  skipInterceptors?: boolean;
}

// ---------------------------------------------------------------------------
// Core request function
// ---------------------------------------------------------------------------

export async function request<T = unknown>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    maxRetries = DEFAULT_MAX_RETRIES,
    forceRetry = false,
    skipInterceptors = false,
    ...fetchOptions
  } = options;

  const url = getApiUrl(path);
  const method = fetchOptions.method || "GET";
  const headers = buildHeaders(method, fetchOptions.headers);
  const canRetry = forceRetry || isRetryableMethod(method);
  const attempts = canRetry ? Math.max(0, maxRetries) + 1 : 1;

  let lastError: ApiError | null = null;

  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      const response = await fetch(url, { ...fetchOptions, headers });

      if (!response.ok) {
        const parsed = await parseErrorPayload(response);
        const apiError = new ApiError({
          status: response.status,
          statusText: response.statusText,
          code: parsed.code,
          detail: parsed.detail,
          payload: parsed.payload,
        });

        // Only retry on retryable errors (5xx / network)
        if (apiError.isRetryable && attempt < attempts - 1) {
          lastError = apiError;
          await sleep(retryDelay(attempt));
          continue;
        }

        // Run global interceptors
        if (!skipInterceptors) {
          const suppressed = await runInterceptors(apiError);
          if (suppressed) return undefined as T;
        }

        throw apiError;
      }

      // Success path
      if (response.status === 204) {
        return undefined as T;
      }

      const ct = response.headers.get("content-type") || "";
      if (!ct.includes("application/json")) {
        return (await response.text()) as unknown as T;
      }

      return (await response.json()) as T;
    } catch (error) {
      // Already an ApiError — re-throw (was thrown above after interceptors)
      if (error instanceof ApiError) {
        throw error;
      }

      // Network-level failure (e.g. DNS, connection refused, CORS)
      const networkError = wrapNetworkError(error);

      if (canRetry && attempt < attempts - 1) {
        lastError = networkError;
        await sleep(retryDelay(attempt));
        continue;
      }

      if (!skipInterceptors) {
        const suppressed = await runInterceptors(networkError);
        if (suppressed) return undefined as T;
      }

      throw networkError;
    }
  }

  // Should not reach here, but just in case
  throw lastError ?? new ApiError({ status: 0, statusText: "Unknown error" });
}

// ---------------------------------------------------------------------------
// Authenticated fetch helper for binary / FormData requests
// ---------------------------------------------------------------------------

/**
 * Perform a raw `fetch` with auth headers attached.
 * Use this for file downloads (Blob responses) and file uploads (FormData).
 */
export async function authenticatedFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const url = getApiUrl(path);
  const headers = buildAuthHeaders(options.headers);

  // For FormData, do NOT set Content-Type — browser sets it with boundary
  if (options.body instanceof FormData) {
    headers.delete("Content-Type");
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const parsed = await parseErrorPayload(response);
    throw new ApiError({
      status: response.status,
      statusText: response.statusText,
      code: parsed.code,
      detail: parsed.detail,
      payload: parsed.payload,
    });
  }

  return response;
}