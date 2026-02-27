/**
 * Fetch wrapper with CSRF double-submit cookie support.
 *
 * Reads the `csrf_token` cookie and adds it as an `X-CSRF-Token` header on
 * all mutating requests (POST, PUT, DELETE, PATCH).  The base URL is read
 * from the `NEXT_PUBLIC_API_URL` environment variable.
 */

/** HTTP methods that require a CSRF token header. */
const MUTATING_METHODS = new Set(["POST", "PUT", "DELETE", "PATCH"]);

/**
 * Read a cookie value by name from `document.cookie`.
 *
 * Returns `null` if the cookie is not found.
 */
function getCookie(name: string): string | null {
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? match.split("=")[1] : null;
}

/**
 * Fetch wrapper that automatically includes credentials and CSRF tokens.
 *
 * @param path - The API path (e.g. `/api/data`).
 * @param init - Standard `RequestInit` options.
 * @returns The `Response` from the underlying `fetch` call.
 */
export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
  const url = `${baseUrl}${path}`;

  const headers = new Headers(init.headers);

  const method = (init.method ?? "GET").toUpperCase();
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = getCookie("csrf_token");
    if (csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  return fetch(url, {
    ...init,
    headers,
    credentials: "include",
  });
}
