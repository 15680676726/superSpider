import "@testing-library/jest-dom/vitest";

if (typeof window !== "undefined") {
  const nativeGetComputedStyle = window.getComputedStyle.bind(window);

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });

  Object.defineProperty(window, "getComputedStyle", {
    configurable: true,
    value: (element: Element, pseudoElement?: string | null) =>
      nativeGetComputedStyle(
        element,
        pseudoElement ? undefined : (pseudoElement ?? undefined),
      ),
  });
}
