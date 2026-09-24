import { getToken } from "./auth";
import type {
  FormattingPrefs,
  HealthInfo,
  PostEditSuggestions,
  PostFilters,
  PostListResponse,
  PostRecord,
  SuggestResponse,
  User,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { ...headers, ...((init?.headers as Record<string, string>) ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body.detail ?? message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  generate: (userQuery: string, filters: PostFilters = {}, language = "English", formatting?: FormattingPrefs) =>
    request<PostRecord>("/posts/generate", {
      method: "POST",
      body: JSON.stringify({
        user_query: userQuery,
        priority: filters.priority ?? undefined,
        post_type: filters.post_type ?? undefined,
        language,
        formatting,
      }),
    }),

  suggest: (text: string, signal?: AbortSignal) =>
    request<SuggestResponse>("/posts/suggest", {
      method: "POST",
      body: JSON.stringify({ text }),
      signal,
    }),

  suggestEdits: (id: string) =>
    request<PostEditSuggestions>(`/posts/${id}/suggest-edits`, {
      method: "POST",
      body: "{}",
    }),

  rework: (id: string, text: string, formatting: FormattingPrefs) =>
    request<PostRecord>(`/posts/${id}/rework`, {
      method: "POST",
      body: JSON.stringify({ text, formatting }),
    }),

  list: (limit = 100, offset = 0, filters: PostFilters = {}) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filters.priority) params.set("priority", filters.priority);
    if (filters.post_type) params.set("post_type", filters.post_type);
    if (filters.status) params.set("status", filters.status);
    return request<PostListResponse>(`/posts?${params}`);
  },

  get: (id: string) => request<PostRecord>(`/posts/${id}`),

  update: (id: string, finalPost: string, hashtags?: string[]) =>
    request<PostRecord>(`/posts/${id}`, {
      method: "PUT",
      body: JSON.stringify({
        final_post: finalPost,
        hashtags: hashtags ?? undefined,
      }),
    }),

  regenerate: (id: string, userQuery?: string) =>
    request<PostRecord>(`/posts/${id}/regenerate`, {
      method: "POST",
      body: JSON.stringify({
        user_query: userQuery,
        regenerate_image: false,
      }),
    }),

  regenerateImage: (id: string) =>
    request<PostRecord>(`/posts/${id}/regenerate-image`, {
      method: "POST",
      body: "{}",
    }),

  approve: (id: string, approved: boolean) =>
    request<PostRecord>(`/posts/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),

  publish: (id: string) =>
    request<PostRecord>(`/posts/${id}/publish`, {
      method: "POST",
      body: JSON.stringify({ approved: true }),
    }),

  health: () => request<HealthInfo>("/health"),

  me: () => request<User>("/auth/me"),
};