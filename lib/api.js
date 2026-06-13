// ModeLens Central API Client
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || ""; // Dynamic or relative fallback

export async function request(endpoint, options = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("modelens_token") : null;

  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers,
  };

  // Handle file uploads (Form Data) where Content-Type shouldn't be set manually
  if (options.body instanceof FormData) {
    delete headers["Content-Type"];
    config.body = options.body;
  } else if (options.body && typeof options.body === "object") {
    config.body = JSON.stringify(options.body);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, config);

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("modelens_token");
      localStorage.removeItem("modelens_user");
      // Trigger redirect if not already on the login page
      if (!window.location.pathname.startsWith("/auth")) {
        window.location.href = `/auth/login?redirect=${encodeURIComponent(
          window.location.pathname + window.location.search
        )}`;
      }
    }
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Unauthorized");
  }

  if (response.status === 429) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || "Rate limit exceeded. Please wait a moment before trying again.";
    throw new Error(errorMessage);
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.detail || errorData.message || `API Error: ${response.statusText}`;
    throw new Error(errorMessage);
  }

  // Some endpoints return empty body or 204 No Content
  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  get: (endpoint, options) => request(endpoint, { ...options, method: "GET" }),
  post: (endpoint, body, options) => request(endpoint, { ...options, method: "POST", body }),
  put: (endpoint, body, options) => request(endpoint, { ...options, method: "PUT", body }),
  patch: (endpoint, body, options) => request(endpoint, { ...options, method: "PATCH", body }),
  delete: (endpoint, options) => request(endpoint, { ...options, method: "DELETE" }),
};
