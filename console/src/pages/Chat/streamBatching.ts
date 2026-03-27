const DEFAULT_FLUSH_INTERVAL_MS = 32;
const DEFAULT_MAX_BUFFER_BYTES = 8 * 1024;

type EventStreamBatchOptions = {
  flushIntervalMs?: number;
  maxBufferBytes?: number;
};

function isEventStreamResponse(response: Response): boolean {
  const contentType = response.headers.get("content-type") || "";
  return contentType.toLowerCase().includes("text/event-stream");
}

function mergeChunks(chunks: Uint8Array[], totalBytes: number): Uint8Array {
  const merged = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return merged;
}

export function coalesceEventStreamResponse(
  response: Response,
  options: EventStreamBatchOptions = {},
): Response {
  if (!response.body || typeof ReadableStream === "undefined") {
    return response;
  }
  if (!isEventStreamResponse(response)) {
    return response;
  }

  const flushIntervalMs = Math.max(
    8,
    options.flushIntervalMs ?? DEFAULT_FLUSH_INTERVAL_MS,
  );
  const maxBufferBytes = Math.max(
    1024,
    options.maxBufferBytes ?? DEFAULT_MAX_BUFFER_BYTES,
  );
  const reader = response.body.getReader();
  const headers = new Headers(response.headers);
  headers.delete("content-length");
  let clearFlushTimerRef = () => {};

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let pendingChunks: Uint8Array[] = [];
      let pendingBytes = 0;
      let flushTimer: number | null = null;

      const clearFlushTimer = () => {
        if (flushTimer !== null) {
          window.clearTimeout(flushTimer);
          flushTimer = null;
        }
      };
      clearFlushTimerRef = clearFlushTimer;

      const flushPending = () => {
        clearFlushTimer();
        if (pendingBytes <= 0) {
          return;
        }
        controller.enqueue(mergeChunks(pendingChunks, pendingBytes));
        pendingChunks = [];
        pendingBytes = 0;
      };

      const scheduleFlush = () => {
        if (flushTimer !== null || pendingBytes <= 0) {
          return;
        }
        flushTimer = window.setTimeout(() => {
          flushPending();
        }, flushIntervalMs);
      };

      const pump = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) {
              break;
            }
            if (!value || value.byteLength <= 0) {
              continue;
            }
            pendingChunks.push(value);
            pendingBytes += value.byteLength;
            if (pendingBytes >= maxBufferBytes) {
              flushPending();
              continue;
            }
            scheduleFlush();
          }
          flushPending();
          controller.close();
        } catch (error) {
          clearFlushTimer();
          controller.error(error);
        } finally {
          reader.releaseLock();
        }
      };

      void pump();
    },
    cancel(reason) {
      clearFlushTimerRef();
      return reader.cancel(reason);
    },
  });

  return new Response(stream, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}
