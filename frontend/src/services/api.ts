import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from "axios";
import { mockDashboard } from "../lib/mockData";
import type { DashboardSnapshot, User } from "../types/domain";

const configuredBaseUrl = import.meta.env.VITE_API_URL as string | undefined;
const baseURL = configuredBaseUrl || (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? "http://localhost:5000/api" : "/api");

export const apiClient: AxiosInstance = axios.create({ baseURL, timeout: 6500, headers: { "Content-Type": "application/json" } });

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("klypup_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("klypup_token");
      window.dispatchEvent(new CustomEvent("klypup:unauthorized"));
    }
    return Promise.reject(error);
  },
);

export const isApiError = (error: unknown): error is AxiosError => axios.isAxiosError(error);

const unwrap = <T>(data: T | { data: T }): T => (typeof data === "object" && data !== null && "data" in data ? data.data : data) as T;

export async function getDashboardSnapshot(config?: AxiosRequestConfig): Promise<DashboardSnapshot> {
  try {
    const response = await apiClient.get<DashboardSnapshot>("/dashboard/summary", config);
    return unwrap(response.data);
  } catch {
    return mockDashboard;
  }
}

export async function getProfile(): Promise<User> {
  const response = await apiClient.get<User>("/auth/profile");
  return unwrap(response.data);
}

export async function loginRequest(email: string, password: string): Promise<{ token: string; user: User }> {
  const response = await apiClient.post<{ token?: string; access_token?: string; user?: User }>("/auth/login", { email, password });
  const data = unwrap(response.data);
  return { token: data.token || data.access_token || "", user: data.user || { id: "remote", name: email.split("@")[0], email, organization: "Klypup workspace", role: "analyst" } };
}

export async function signupRequest(payload: { name: string; email: string; password: string; organization: string }): Promise<{ token: string; user: User }> {
  const response = await apiClient.post<{ token?: string; access_token?: string; user?: User }>("/auth/register", { ...payload, organization_name: payload.organization });
  const data = unwrap(response.data);
  return { token: data.token || data.access_token || "", user: data.user || { id: "remote", name: payload.name, email: payload.email, organization: payload.organization, role: "admin" } };
}

export default apiClient;
