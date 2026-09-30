// Validates post-login redirect targets so only same-origin paths are followed.
export const DEFAULT_REDIRECT = "/dashboard";

const PLACEHOLDER_ORIGIN = "http://modelens.internal";

export function safeRedirect(target, fallback = DEFAULT_REDIRECT) {
  if (typeof target !== "string" || target.length === 0) return fallback;

  // Must be a root-relative path. Rejects absolute URLs, protocol-relative
  // "//host", backslash tricks ("/\host"), and control characters.
  if (!target.startsWith("/") || target.startsWith("//")) return fallback;
  if (/[\\\u0000-\u001f\u007f]/.test(target)) return fallback;

  let url;
  try {
    url = new URL(target, PLACEHOLDER_ORIGIN);
  } catch {
    return fallback;
  }
  if (url.origin !== PLACEHOLDER_ORIGIN) return fallback;

  // Never bounce back into the auth pages themselves.
  if (url.pathname === "/auth" || url.pathname.startsWith("/auth/")) return fallback;

  return url.pathname + url.search + url.hash;
}

export function loginUrlFor(target) {
  const redirect = safeRedirect(target, null);
  return redirect ? `/auth/login?redirect=${encodeURIComponent(redirect)}` : "/auth/login";
}
