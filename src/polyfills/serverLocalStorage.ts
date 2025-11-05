// Ensures Node.js provides a Storage-like implementation when the new global
// `localStorage` shim is present but missing the standard methods (e.g. when
// `--localstorage-file` is unset).
if (typeof window === 'undefined') {
  const globalLocalStorage = (globalThis as Record<string, unknown>).localStorage;

  if (
    globalLocalStorage &&
    (typeof (globalLocalStorage as Storage).getItem !== 'function' ||
      typeof (globalLocalStorage as Storage).setItem !== 'function')
  ) {
    const memoryStore = new Map<string, string>();

    const memoryLocalStorage: Storage = {
      get length() {
        return memoryStore.size;
      },
      clear() {
        memoryStore.clear();
      },
      getItem(key: string) {
        return memoryStore.has(key) ? memoryStore.get(key)! : null;
      },
      key(index: number) {
        return Array.from(memoryStore.keys())[index] ?? null;
      },
      removeItem(key: string) {
        memoryStore.delete(key);
      },
      setItem(key: string, value: string) {
        memoryStore.set(key, String(value));
      },
    };

    (globalThis as Record<string, unknown>).localStorage = memoryLocalStorage;
  }
}
