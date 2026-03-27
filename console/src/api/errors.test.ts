import { describe, it, expect } from "vitest";
import { ApiError, wrapNetworkError, isApiError } from "../api/errors";

describe("ApiError", () => {
  it("stores status, code, detail, and payload", () => {
    const err = new ApiError({
      status: 422,
      statusText: "Unprocessable Entity",
      code: "VALIDATION_FAILED",
      detail: "field X is required",
      payload: { field: "X" },
    });
    expect(err.status).toBe(422);
    expect(err.code).toBe("VALIDATION_FAILED");
    expect(err.detail).toBe("field X is required");
    expect(err.payload).toEqual({ field: "X" });
    expect(err.message).toBe("[422] field X is required");
    expect(err.name).toBe("ApiError");
  });

  it("falls back to statusText when detail is empty", () => {
    const err = new ApiError({ status: 500, statusText: "Internal Server Error" });
    expect(err.detail).toBe("Internal Server Error");
    expect(err.code).toBe("");
    expect(err.payload).toBeNull();
  });

  it("isUnauthorized / isForbidden / isNotFound", () => {
    expect(new ApiError({ status: 401, statusText: "" }).isUnauthorized).toBe(true);
    expect(new ApiError({ status: 403, statusText: "" }).isForbidden).toBe(true);
    expect(new ApiError({ status: 404, statusText: "" }).isNotFound).toBe(true);
    expect(new ApiError({ status: 200, statusText: "" }).isUnauthorized).toBe(false);
  });

  it("isServerError for 5xx range", () => {
    expect(new ApiError({ status: 500, statusText: "" }).isServerError).toBe(true);
    expect(new ApiError({ status: 503, statusText: "" }).isServerError).toBe(true);
    expect(new ApiError({ status: 499, statusText: "" }).isServerError).toBe(false);
    expect(new ApiError({ status: 600, statusText: "" }).isServerError).toBe(false);
  });

  it("isNetworkError for status 0", () => {
    expect(new ApiError({ status: 0, statusText: "" }).isNetworkError).toBe(true);
    expect(new ApiError({ status: 0, statusText: "" }).isRetryable).toBe(true);
  });

  it("isRetryable for network errors and 5xx", () => {
    expect(new ApiError({ status: 0, statusText: "" }).isRetryable).toBe(true);
    expect(new ApiError({ status: 502, statusText: "" }).isRetryable).toBe(true);
    expect(new ApiError({ status: 401, statusText: "" }).isRetryable).toBe(false);
    expect(new ApiError({ status: 404, statusText: "" }).isRetryable).toBe(false);
  });

  it("is an instance of Error", () => {
    const err = new ApiError({ status: 400, statusText: "Bad Request" });
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
  });
});

describe("wrapNetworkError", () => {
  it("wraps a native Error into ApiError with status 0", () => {
    const native = new TypeError("Failed to fetch");
    const wrapped = wrapNetworkError(native);
    expect(wrapped).toBeInstanceOf(ApiError);
    expect(wrapped.status).toBe(0);
    expect(wrapped.detail).toBe("Failed to fetch");
    expect(wrapped.isNetworkError).toBe(true);
  });

  it("wraps a non-Error value", () => {
    const wrapped = wrapNetworkError("something broke");
    expect(wrapped.status).toBe(0);
    expect(wrapped.detail).toBe("Network request failed");
  });
});

describe("isApiError", () => {
  it("returns true for ApiError instances", () => {
    expect(isApiError(new ApiError({ status: 400, statusText: "" }))).toBe(true);
  });

  it("returns false for plain errors and other values", () => {
    expect(isApiError(new Error("nope"))).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError({ status: 400 })).toBe(false);
  });
});
