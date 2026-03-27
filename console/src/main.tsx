import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import {
  isChunkLoadError,
  reloadForChunkError,
} from "./runtime/chunkLoadRecovery";
import { installGlobalErrorInterceptor } from "./runtime/globalErrorInterceptor";
import { startEventBus } from "./runtime/eventBus";
import { useAppStore } from "./stores";

// ---------------------------------------------------------------------------
// Global error recovery for chunk load failures
// ---------------------------------------------------------------------------

if (typeof window !== "undefined") {
  window.addEventListener("unhandledrejection", (event) => {
    if (!isChunkLoadError(event.reason)) return;
    event.preventDefault();
    reloadForChunkError();
  });

  window.addEventListener("error", (event) => {
    if (!isChunkLoadError(event.error || event.message)) return;
    reloadForChunkError();
  });
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

async function bootstrap() {
  // Install global API error interceptor (401/403/5xx toasts)
  installGlobalErrorInterceptor();

  // Start SSE event bus for real-time updates
  startEventBus();

  // Kick off app-level data loading (version, system overview)
  void useAppStore.getState().bootstrap();

  // Render
  createRoot(document.getElementById("root")!).render(<App />);
}

void bootstrap();
