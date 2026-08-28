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
  onboarding_completed?: boolean;
  store_platform?: string | null;
  store_domain?: string | null;
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
  recommendationId?: string;
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

export interface ApprovalAuditEvent {
  id: string;
  recommendationId: string;
  actionType: "approve" | "reject" | "rollback" | "auto_execute";
  sku: string;
  productName: string;
  previousPrice: number;
  executedPrice: number;
  llmStatement: string;
  userEmail: string;
  emailSentStatus: "pending" | "sent" | "mocked" | "failed";
  timestamp: string;
  rolledBack?: boolean;
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


export type RecommendationJobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";
export type AgentEventStatus = "pending" | "running" | "succeeded" | "failed" | "skipped";

export interface RecommendationAgentEvent {
  id: string;
  agent_name: string;
  status: AgentEventStatus;
  progress: number;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface MarketplaceOffer {
  id: string;
  job_id: string;
  product_id: string;
  platform: string;
  title?: string | null;
  brand?: string | null;
  variant?: string | null;
  current_price?: number | null;
  mrp?: number | null;
  availability?: string | null;
  in_stock?: boolean | null;
  specifications?: Record<string, unknown>;
  images?: string[];
  rating?: number | null;
  review_count?: number | null;
  offers?: Array<Record<string, unknown>>;
  product_url?: string | null;
  match_confidence?: string | null;
  source_type?: string | null;
  fetched_at: string;
}

export interface RecommendationJob {
  id: string;
  recommendation_id: string;
  product_id: string;
  status: RecommendationJobStatus;
  progress: number;
  current_agent?: string | null;
  requested_platforms: string[];
  attempts: number;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  recommendation?: { status?: string | null } | null;
  events: RecommendationAgentEvent[];
  offers: MarketplaceOffer[];
}
