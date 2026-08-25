import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from "axios";
import { mockDashboard } from "../lib/mockData";
import type { ActivityItem, DashboardSnapshot, PriceDropAlert, Product, User } from "../types/domain";

const configuredBaseUrl = import.meta.env.VITE_API_URL as string | undefined;
const baseURL = configuredBaseUrl || (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" ? "http://localhost:5000/api" : "/api");
export const apiClient: AxiosInstance = axios.create({ baseURL, timeout: 6500, headers: { "Content-Type": "application/json" } });

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("klypup_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
apiClient.interceptors.response.use((response) => response, (error: AxiosError) => {
  if (error.response?.status === 401) { localStorage.removeItem("klypup_token"); window.dispatchEvent(new CustomEvent("klypup:unauthorized")); }
  return Promise.reject(error);
});
export const isApiError = (error: unknown): error is AxiosError => axios.isAxiosError(error);
type Wrapped<T> = T | { data: T };
const unwrap = <T>(data: Wrapped<T>): T => (typeof data === "object" && data !== null && "data" in data ? data.data : data) as T;

interface BackendMetrics { totalRevenue: number; pricingAccuracy: number; marketVolatility: number; aiConfidence: number; competitorChanges: number; conversionRate: number; liveProducts: number; totalInventory: number; reviewsQueueCount: number; aiSignalsStrength: number; activeModelsCount: number; }
interface BackendRevenuePoint { date: string; actual: number; predicted: number; }
interface BackendProduct { id: string; sku?: string; name: string; category?: string; current_price?: number; cost_price?: number; inventory_quantity?: number; margin_percentage?: number; recommendation_status?: string; }
interface BackendRecommendation { id: string; productName?: string; product?: { name?: string; id?: string; current_price?: number }; currentPrice?: number; suggestedPrice?: number; recommended_price?: number; confidence?: number; confidence_score?: number; reason?: string; }
interface BackendActivity { message: string; timestamp: string; type: string; }

const moneyValue = (value: number) => value >= 1_000_000 ? `$${(value / 1_000_000).toFixed(2)}m` : `$${(value / 1_000).toFixed(1)}k`;
const initials = (name: string) => name.split(/\s+/).map((word) => word[0]).join("").slice(0, 2).toUpperCase();
const gradientFor = (category: string) => ({ electronics: "linear-gradient(135deg,#be123c,#fb7185)", apparel: "linear-gradient(135deg,#7c3aed,#c084fc)", beauty: "linear-gradient(135deg,#db2777,#f9a8d4)", sports: "linear-gradient(135deg,#0f766e,#2dd4bf)", home_goods: "linear-gradient(135deg,#059669,#34d399)" }[category.toLowerCase()] || "linear-gradient(135deg,#4338ca,#818cf8)");

const toProduct = (item: BackendProduct, recommendations: BackendRecommendation[]): Product => {
  const match = recommendations.find((recommendation) => recommendation.product?.id === item.id || recommendation.productName === item.name);
  const status = item.recommendation_status === "approved" ? "approved" : item.recommendation_status === "pending" ? "recommended" : "monitor";
  const currentPrice = Number(item.current_price || 0);
  return { id: item.id, sku: item.sku || "UNASSIGNED", name: item.name, category: (item.category || "General").replace(/_/g, " "), initials: initials(item.name), image: gradientFor(item.category || "general"), currentPrice, targetPrice: Number(match?.suggestedPrice ?? match?.recommended_price ?? currentPrice), margin: Number(item.margin_percentage ?? (currentPrice ? ((currentPrice - Number(item.cost_price || 0)) / currentPrice) * 100 : 0)), inventory: Number(item.inventory_quantity || 0), status, confidence: Number(match?.confidence ?? match?.confidence_score ?? (status === "approved" ? 90 : 72)) };
};
const toActivity = (item: BackendActivity, index: number): ActivityItem => { const raw = item.type.toLowerCase(); const kind = raw.includes("compet") ? "competitor" : raw.includes("invent") ? "inventory" : raw.includes("price") || raw.includes("recommend") ? "repriced" : "system"; const severity = kind === "competitor" || kind === "inventory" ? "warning" : kind === "repriced" ? "positive" : "neutral"; return { id: `backend-activity-${index}-${item.timestamp}`, kind, title: item.message, detail: `Live event from the ${item.type || "pricing"} stream.`, time: item.timestamp ? new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "just now", severity }; };

export async function getDashboardSnapshot(config?: AxiosRequestConfig): Promise<DashboardSnapshot> {
  try {
    const metrics = (await apiClient.get<BackendMetrics>("/dashboard/metrics", config)).data;
    const revenue = unwrap((await apiClient.get<Wrapped<BackendRevenuePoint[]>>("/dashboard/revenue", config)).data);
    const rawProducts = unwrap((await apiClient.get<Wrapped<{ products?: BackendProduct[] } | BackendProduct[]>>("/products", config)).data);
    const products = Array.isArray(rawProducts) ? rawProducts : rawProducts.products || [];
    const rawRecommendations = unwrap((await apiClient.get<Wrapped<{ recommendations?: BackendRecommendation[] } | BackendRecommendation[]>>("/recommendations", config)).data);
    const recommendations = Array.isArray(rawRecommendations) ? rawRecommendations : rawRecommendations.recommendations || [];
    const activityResponse = await apiClient.get<{ feed?: BackendActivity[] }>("/dashboard/live-activity", config);
    const kpis = [
      { label: "Total revenue", value: moneyValue(metrics.totalRevenue), rawValue: metrics.totalRevenue, delta: metrics.conversionRate, trend: "up" as const, description: "catalog value run-rate", accent: "indigo" as const },
      { label: "Active price models", value: String(metrics.activeModelsCount), rawValue: metrics.activeModelsCount, delta: metrics.aiSignalsStrength - 90, trend: "up" as const, description: `${metrics.reviewsQueueCount} recommendations to review`, accent: "violet" as const },
      { label: "Pricing accuracy", value: `${metrics.pricingAccuracy.toFixed(1)}%`, rawValue: metrics.pricingAccuracy, delta: metrics.aiConfidence - metrics.pricingAccuracy, trend: "up" as const, description: `${metrics.aiConfidence.toFixed(1)}% AI confidence`, accent: "emerald" as const },
      { label: "Live products", value: metrics.liveProducts.toLocaleString(), rawValue: metrics.liveProducts, delta: metrics.marketVolatility, trend: metrics.marketVolatility > 25 ? "down" as const : "up" as const, description: `${metrics.totalInventory.toLocaleString()} units in inventory`, accent: "rose" as const },
    ];
    const chart = revenue.map((point) => ({ label: point.date, revenue: Number(point.actual || 0), elasticity: Number(point.actual ? (point.predicted / point.actual).toFixed(2) : 1), margin: Number(metrics.pricingAccuracy || 0) }));
    return { kpis, chart, products: products.map((item) => toProduct(item, recommendations)), activity: (activityResponse.data.feed || []).map(toActivity), systemHealth: metrics.marketVolatility > 30 ? "attention" : "healthy", updatedAt: "Just now" };
  } catch { return mockDashboard; }
}

interface BackendPriceDropAlert { id: string; product_id: string; product_name: string; sku: string; competitor_name: string; previous_price: number; current_price: number; drop_percent: number; drop_amount: number; threshold_percent: number; status: "open" | "acknowledged"; detected_at: string; acknowledged_at?: string | null; }

const toPriceDropAlert = (alert: BackendPriceDropAlert): PriceDropAlert => ({ id: alert.id, productId: alert.product_id, productName: alert.product_name, sku: alert.sku, competitorName: alert.competitor_name, previousPrice: Number(alert.previous_price), currentPrice: Number(alert.current_price), dropPercent: Number(alert.drop_percent), dropAmount: Number(alert.drop_amount), thresholdPercent: Number(alert.threshold_percent), status: alert.status, detectedAt: alert.detected_at, acknowledgedAt: alert.acknowledged_at });

export async function getPriceDropAlerts(status: "open" | "acknowledged" | "all" = "open"): Promise<PriceDropAlert[]> { const response = await apiClient.get<{ alerts?: BackendPriceDropAlert[] }>(`/alerts?status=${status}`); return (response.data.alerts || []).map(toPriceDropAlert); }
export async function scanPriceDropAlerts(payload: { productId: string; previousPrices: Record<string, number>; observations: Record<string, number>; thresholdPct?: number; minDropInr?: number }): Promise<PriceDropAlert[]> { const response = await apiClient.post<{ alerts?: BackendPriceDropAlert[] }>("/alerts/scan", { product_id: payload.productId, previous_prices: payload.previousPrices, observations: payload.observations, threshold_pct: payload.thresholdPct, min_drop_inr: payload.minDropInr }); return (response.data.alerts || []).map(toPriceDropAlert); }
export async function acknowledgePriceDropAlert(id: string): Promise<PriceDropAlert> { const response = await apiClient.patch<{ alert: BackendPriceDropAlert }>(`/alerts/${id}/acknowledge`); return toPriceDropAlert(response.data.alert); }

export async function getProfile(): Promise<User> { const response = await apiClient.get<Wrapped<{ user?: User } | User>>("/auth/profile"); const data = unwrap(response.data); return (typeof data === "object" && data !== null && "user" in data ? data.user : data) as User; }
export async function loginRequest(email: string, password: string): Promise<{ token: string; user: User }> { const response = await apiClient.post<{ token?: string; access_token?: string; user?: User }>("/auth/login", { email, password }); const data = unwrap(response.data); return { token: data.token || data.access_token || "", user: data.user || { id: "remote", name: email.split("@")[0], email, organization: "Klypup workspace", role: "analyst" } }; }
export async function signupRequest(payload: { name: string; email: string; password: string; organization: string }): Promise<{ token: string; user: User }> { const response = await apiClient.post<{ token?: string; access_token?: string; user?: User }>("/auth/register", { ...payload, organization_name: payload.organization }); const data = unwrap(response.data); return { token: data.token || data.access_token || "", user: data.user || { id: "remote", name: payload.name, email: payload.email, organization: payload.organization, role: "admin" } }; }
export default apiClient;
