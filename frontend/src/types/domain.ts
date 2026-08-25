export type Trend = "up" | "down" | "flat";
export type Health = "healthy" | "attention" | "offline";
export type TimeRange = "24h" | "7d" | "30d" | "1y";
export type ActivityKind = "repriced" | "competitor" | "inventory" | "system";

export interface User {
  id: string;
  name: string;
  email: string;
  organization: string;
  role: "admin" | "analyst" | "viewer";
  avatar?: string;
}

export interface Kpi {
  label: string;
  value: string;
  rawValue: number;
  delta: number;
  trend: Trend;
  description: string;
  accent: "indigo" | "emerald" | "rose" | "violet";
}

export interface ChartPoint {
  label: string;
  revenue: number;
  elasticity: number;
  margin: number;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  category: string;
  initials: string;
  image: string;
  currentPrice: number;
  targetPrice: number;
  margin: number;
  inventory: number;
  status: "recommended" | "approved" | "monitor";
  confidence: number;
}

export interface ActivityItem {
  id: string;
  kind: ActivityKind;
  title: string;
  detail: string;
  time: string;
  severity: "positive" | "neutral" | "warning";
}

export interface DashboardSnapshot {
  kpis: Kpi[];
  chart: ChartPoint[];
  products: Product[];
  activity: ActivityItem[];
  systemHealth: Health;
  updatedAt: string;
}

export interface StrategyPreset {
  id: string;
  name: string;
  summary: string;
  icon: "zap" | "shield" | "waves" | "archive";
  color: "indigo" | "emerald" | "violet" | "rose";
  active: boolean;
  guardrail: string;
  expectedLift: string;
}

export interface CompetitorRow {
  id: string;
  product: string;
  category: string;
  store: number;
  amazon: number;
  walmart: number;
  target: number;
  flag: "cheaper" | "matched" | "premium";
  scraped: string;
}

export interface ScraperAgent {
  id: string;
  marketplace: string;
  cadence: string;
  lastScraped: string;
  health: Health;
  rotation: string;
  coverage: number;
}

export interface PriceDropAlert {
  id: string;
  productId: string;
  productName: string;
  sku: string;
  competitorName: string;
  previousPrice: number;
  currentPrice: number;
  dropPercent: number;
  dropAmount: number;
  thresholdPercent: number;
  status: "open" | "acknowledged";
  detectedAt: string;
  acknowledgedAt?: string | null;
}

export interface Integration {
  id: "shopify" | "woocommerce" | "amazon";
  name: string;
  description: string;
  connected: boolean;
  color: string;
}
