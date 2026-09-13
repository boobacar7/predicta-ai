const AUTH_STORAGE_KEYS = ["predicta_session", "access_token", "id_token", "jwt", "auth_token"] as const;

export function readCookie(name: string, cookieHeader = typeof document === "undefined" ? "" : document.cookie): string | undefined {
  if (!cookieHeader) return undefined;
  const prefix = `${name}=`;
  const match = cookieHeader.split("; ").find((part) => part.startsWith(prefix));
  if (!match) return undefined;
  return decodeURIComponent(match.slice(prefix.length));
}

/** Auth tokens must never be written to localStorage. Theme may still use it. */
export function assertNoAuthTokenStorage(storage: Pick<Storage, "getItem" | "key" | "length">): string[] {
  const hits: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key && AUTH_STORAGE_KEYS.includes(key as (typeof AUTH_STORAGE_KEYS)[number])) {
      hits.push(key);
    }
  }
  for (const key of AUTH_STORAGE_KEYS) {
    if (storage.getItem(key)) hits.push(key);
  }
  return [...new Set(hits)];
}
