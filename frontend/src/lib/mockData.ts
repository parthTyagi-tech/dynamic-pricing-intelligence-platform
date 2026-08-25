import type {
  ActivityItem,
  CompetitorRow,
  DashboardSnapshot,
  Integration,
  ScraperAgent,
  StrategyPreset,
} from "../types/domain";

const curve = (base: number, swing: number, count = 12) =>
  Array.from({ length: count }, (_, index) => ({
    label: `${String(index * 2).padStart(2, "0")}:00`,
    revenue: Math.round(base + Math.sin(index * 0.7) * swing + index * 420),
    elasticity: Number((1.08 + Math.cos(index * 0.48) * 0.2).toFixed(2)),
    margin: Number((26 + Math.sin(index * 0.32) * 3 + index * 0.12).toFixed(1)),
  }));

export const mockDashboard: DashboardSnapshot = {
  kpis: [
    { label: "Total revenue", value: "$428.6k", rawValue: 428600, delta: 12.4, trend: "up", description: "vs previous period", accent: "indigo" },
    { label: "Active price rules", value: "24", rawValue: 24, delta: 8.1, trend: "up", description: "3 need review", accent: "violet" },
    { label: "Margin lift", value: "+7.8%", rawValue: 7.8, delta: 2.6, trend: "up", description: "blended catalog", accent: "emerald" },
    { label: "AI repriced items", value: "1,284", rawValue: 1284, delta: -3.2, trend: "down", description: "last 30 days", accent: "rose" },
  ],
  chart: curve(31500, 2200),
  products: [
    { id: "p-1", sku: "SKU-2048", name: "AeroFlex Running Shoe", category: "Footwear", initials: "AF", image: "linear-gradient(135deg,#4338ca,#818cf8)", currentPrice: 124, targetPrice: 131, margin: 31.4, inventory: 82, status: "recommended", confidence: 94 },
    { id: "p-2", sku: "SKU-1093", name: "Luma Desk Lamp", category: "Home", initials: "LD", image: "linear-gradient(135deg,#059669,#34d399)", currentPrice: 49, targetPrice: 46, margin: 27.8, inventory: 214, status: "approved", confidence: 88 },
    { id: "p-3", sku: "SKU-7712", name: "CloudWeave Hoodie", category: "Apparel", initials: "CW", image: "linear-gradient(135deg,#7c3aed,#c084fc)", currentPrice: 76, targetPrice: 81, margin: 35.2, inventory: 38, status: "monitor", confidence: 79 },
    { id: "p-4", sku: "SKU-5520", name: "Pulse Pro Earbuds", category: "Electronics", initials: "PP", image: "linear-gradient(135deg,#be123c,#fb7185)", currentPrice: 89, targetPrice: 93, margin: 24.6, inventory: 146, status: "recommended", confidence: 91 },
    { id: "p-5", sku: "SKU-3381", name: "Terra Steel Bottle", category: "Outdoors", initials: "TS", image: "linear-gradient(135deg,#0f766e,#2dd4bf)", currentPrice: 35, targetPrice: 32, margin: 42.1, inventory: 306, status: "approved", confidence: 86 },
    { id: "p-6", sku: "SKU-9001", name: "Orbit Travel Pack", category: "Accessories", initials: "OT", image: "linear-gradient(135deg,#c2410c,#fb923c)", currentPrice: 112, targetPrice: 118, margin: 29.2, inventory: 29, status: "recommended", confidence: 82 },
  ],
  activity: [
    { id: "a-1", kind: "repriced", title: "AI repriced 18 SKUs", detail: "Margin Guard moved the footwear cluster up 4.2%.", time: "2m ago", severity: "positive" },
    { id: "a-2", kind: "competitor", title: "Competitor undercut detected", detail: "Amazon is $6 below target on Pulse Pro Earbuds.", time: "8m ago", severity: "warning" },
    { id: "a-3", kind: "inventory", title: "Low inventory signal", detail: "Orbit Travel Pack crossed the 30-unit threshold.", time: "21m ago", severity: "warning" },
    { id: "a-4", kind: "system", title: "Scraper sync completed", detail: "1,248 competitor records refreshed successfully.", time: "34m ago", severity: "neutral" },
    { id: "a-5", kind: "repriced", title: "Approval queue updated", detail: "4 high-confidence recommendations are ready.", time: "51m ago", severity: "positive" },
  ],
  systemHealth: "healthy",
  updatedAt: "Just now",
};

export const strategyPresets: StrategyPreset[] = [
  { id: "competitive", name: "Aggressive Competitive", summary: "Win the buy box with controlled undercuts.", icon: "zap", color: "indigo", active: true, guardrail: "Min. margin 18%", expectedLift: "+9.4% revenue" },
  { id: "margin", name: "Margin Guard", summary: "Protect profit while demand stays resilient.", icon: "shield", color: "emerald", active: true, guardrail: "Max discount 6%", expectedLift: "+3.8% margin" },
  { id: "elastic", name: "Elastic Demand", summary: "Lean into price sensitivity by segment.", icon: "waves", color: "violet", active: false, guardrail: "Confidence > 82%", expectedLift: "+6.1% units" },
  { id: "clearance", name: "Inventory Clearance", summary: "Move slow stock without eroding the brand.", icon: "archive", color: "rose", active: false, guardrail: "Stock > 120 days", expectedLift: "-42 days cover" },
];

export const competitorRows: CompetitorRow[] = [
  { id: "c-1", product: "AeroFlex Running Shoe", category: "Footwear", store: 124, amazon: 131, walmart: 129, target: 131, flag: "cheaper", scraped: "2m ago" },
  { id: "c-2", product: "Pulse Pro Earbuds", category: "Electronics", store: 89, amazon: 83, walmart: 91, target: 93, flag: "premium", scraped: "4m ago" },
  { id: "c-3", product: "Luma Desk Lamp", category: "Home", store: 49, amazon: 49, walmart: 52, target: 46, flag: "matched", scraped: "8m ago" },
  { id: "c-4", product: "CloudWeave Hoodie", category: "Apparel", store: 76, amazon: 72, walmart: 79, target: 81, flag: "premium", scraped: "11m ago" },
  { id: "c-5", product: "Terra Steel Bottle", category: "Outdoors", store: 35, amazon: 39, walmart: 37, target: 32, flag: "cheaper", scraped: "14m ago" },
];

export const scraperAgents: ScraperAgent[] = [
  { id: "s-1", marketplace: "Amazon", cadence: "Every 5 minutes", lastScraped: "2 minutes ago", health: "healthy", rotation: "Rotating · US-East", coverage: 98 },
  { id: "s-2", marketplace: "Walmart", cadence: "Every 15 minutes", lastScraped: "8 minutes ago", health: "healthy", rotation: "Rotating · US-Central", coverage: 94 },
  { id: "s-3", marketplace: "Target", cadence: "Every 30 minutes", lastScraped: "27 minutes ago", health: "attention", rotation: "Idle · US-West", coverage: 87 },
];

export const integrations: Integration[] = [
  { id: "shopify", name: "Shopify", description: "Sync catalog, inventory, and live price updates.", connected: true, color: "#95BF47" },
  { id: "woocommerce", name: "WooCommerce", description: "Connect a WordPress storefront through REST API.", connected: false, color: "#96588A" },
  { id: "amazon", name: "Amazon Seller", description: "Monitor marketplace competition and buy box position.", connected: false, color: "#FF9900" },
];
