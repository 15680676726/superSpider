import { onResponseError } from "../api";
import type { ApiError } from "../api";
import { useAppStore } from "../stores";

let installed = false;

/**
 * Install global API response-error interceptors.
 * Call once at app bootstrap (e.g. in main.tsx or App.tsx).
 *
 * - 401 → redirect to login (or show auth toast)
 * - 403 → permission denied toast
 * - 0   → network error toast
 * - 5xx → server error toast
 */
export function installGlobalErrorInterceptor(): () => void {
  if (installed) return () => {};
  installed = true;

  const unsubscribe = onResponseError((error: ApiError) => {
    // Import message lazily to avoid circular deps with antd
    import("antd").then(({ message }) => {
      if (error.isUnauthorized) {
        message.error("登录已过期，请重新登录");
        // Could redirect: window.location.href = "/login";
        return;
      }

      if (error.isForbidden) {
        message.error("没有权限执行此操作");
        return;
      }

      if (error.isNetworkError) {
        const appStore = useAppStore.getState();
        if (!appStore.online) {
          // Already showing offline banner — skip duplicate toast
          return;
        }
        message.error("网络连接失败，请检查网络后重试");
        return;
      }

      if (error.isServerError) {
        message.error(
          error.detail || `服务器错误 (${error.status})`,
        );
        return;
      }
    });

    // Don't suppress — let callers handle too
    return false;
  });

  return () => {
    installed = false;
    unsubscribe();
  };
}
