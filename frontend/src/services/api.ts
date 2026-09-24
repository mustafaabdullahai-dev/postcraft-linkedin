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
  VoiceProfile,
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
  generate: (userQuery: string, filters: PostFilters = {}, language = "English", formatting?: FormattingPrefs, voiceProfileId?: string) =>
    request<PostRecord>("/posts/generate", {
      method: "POST",
      body: JSON.stringify({
        user_query: userQuery,
        priority: filters.priority ?? undefined,
        post_type: filters.post_type ?? undefined,
        language,
        formatting,
        voice_profile_id: voiceProfileId ?? undefined,
      }),
    }),

  batchGenerate: (userQuery: string, variations: number, filters: PostFilters = {}, language = "English", formatting?: FormattingPrefs, voiceProfileId?: string) =>
    request<{ items: PostRecord[] }>("/posts/batch-generate", {
      method: "POST",
      body: JSON.stringify({
        user_query: userQuery,
        variations,
        priority: filters.priority ?? undefined,
        post_type: filters.post_type ?? undefined,
        language,
        formatting,
        voice_profile_id: voiceProfileId ?? undefined,
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
    if (filters.q) params.set("q", filters.q);
    if (filters.sort) params.set("sort", filters.sort);
    if (filters.from_date) params.set("from_date", filters.from_date);
    if (filters.to_date) params.set("to_date", filters.to_date);
    return request<PostListResponse>(`/posts?${params}`);
  },

  get: (id: string) => request<PostRecord>(`/posts/${id}`),

  deletePost: (id: string) =>
    request<{ ok: boolean; record_id: string }>(`/posts/${id}`, { method: "DELETE" }),

  deleteAll: (filters: PostFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.priority) params.set("priority", filters.priority);
    if (filters.post_type) params.set("post_type", filters.post_type);
    if (filters.status) params.set("status", filters.status);
    if (filters.q) params.set("q", filters.q);
    return request<{ ok: boolean; deleted: number }>(`/posts?${params}`, { method: "DELETE" });
  },

  duplicatePost: (id: string) =>
    request<PostRecord>(`/posts/${id}/duplicate`, {
      method: "POST",
      body: "{}",
    }),

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

  regenerateImage: (id: string, prompt?: string) =>
    request<PostRecord>(`/posts/${id}/regenerate-image`, {
      method: "POST",
      body: JSON.stringify(prompt?.trim() ? { prompt: prompt.trim() } : {}),
    }),

  approve: (id: string, approved: boolean, scheduledAt?: string) =>
    request<PostRecord>(`/posts/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({
        approved,
        scheduled_at: scheduledAt ?? null,
      }),
    }),

  publish: (id: string) =>
    request<PostRecord>(`/posts/${id}/publish`, {
      method: "POST",
      body: JSON.stringify({ approved: true }),
    }),

  voiceProfiles: {
    list: () => request<VoiceProfile[]>("/voice-profiles"),
    create: (data: Partial<VoiceProfile>) =>
      request<VoiceProfile>("/voice-profiles", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<VoiceProfile>) =>
      request<VoiceProfile>(`/voice-profiles/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    remove: (id: string) =>
      request<{ ok: boolean }>(`/voice-profiles/${id}`, { method: "DELETE" }),
  },

  downloadExport: async (format: "csv" | "json" | "md") => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(`/api/posts/export?format=${format}`, {
      credentials: "include",
      headers,
    });
    if (!res.ok) {
      let message = `Export failed (${res.status})`;
      try {
        const body = await res.json();
        message = body.detail ?? message;
      } catch {
        /* ignore */
      }
      throw new Error(message);
    }
    const disposition = res.headers.get("content-disposition") ?? "";
    const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `posts.${format}`;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  health: () => request<HealthInfo>("/health"),

  me: () => request<User>("/auth/me"),
};