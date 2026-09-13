import { HttpClient } from "@/data/http/client";
import { getConfig } from "@/lib/config";
import type { Envelope } from "@/types/api";

export interface AuthUser {
  id: string;
  email: string;
}

export interface LoginResult {
  user: AuthUser;
  csrf_token: string;
}

export interface LogoutResult {
  logged_out: boolean;
}

export interface AuthSessionResult {
  user: AuthUser | null;
  bypass: boolean;
}

let client: HttpClient | undefined;

function authClient(): HttpClient {
  const config = getConfig();
  client ??= new HttpClient({
    baseUrl: config.apiBaseUrl,
    requestTimeoutMs: config.requestTimeoutMs,
    csrfCookieName: config.csrfCookieName,
    csrfHeaderName: config.csrfHeaderName,
  });
  return client;
}

export function resetAuthClient(): void {
  client = undefined;
}

export function loginWithPassword(email: string, password: string): Promise<Envelope<LoginResult>> {
  return authClient().post<LoginResult>("/auth/login", { email, password });
}

export function logoutSession(): Promise<Envelope<LogoutResult>> {
  return authClient().post<LogoutResult>("/auth/logout");
}

export function fetchAuthSession(): Promise<Envelope<AuthSessionResult>> {
  return authClient().get<AuthSessionResult>("/auth/session");
}

export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/login")) {
    return "/";
  }
  return value;
}
