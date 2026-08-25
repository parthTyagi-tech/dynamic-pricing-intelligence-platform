const productSeed = [
  {
    sku: "SKU-9402",
    productName: "AeroSound Pro Headphones",
    category: "Electronics",
    currentPrice: 148,
    suggestedPrice: 143.26,
    confidence: 96,
    volumeLift: 18,
    marginDelta: 2.4,
    rationale: "Lower price by 3.2% to capture +18% unit volume while protecting the margin floor.",
    status: "PENDING",
  },
  {
    sku: "SKU-1884",
    productName: "Nimbus Knit Runner",
    category: "Apparel",
    currentPrice: 96,
    suggestedPrice: 101.75,
    confidence: 91,
    volumeLift: 9,
    marginDelta: 4.8,
    rationale: "Demand velocity is accelerating and the market is carrying a $6.40 premium.",
    status: "PENDING",
  },
  {
    sku: "SKU-7021",
    productName: "LumaDesk Task Light",
    category: "Home",
    currentPrice: 64,
    suggestedPrice: 59.9,
    confidence: 87,
    volumeLift: 14,
    marginDelta: 1.1,
    rationale: "Match the market median before the weekend traffic spike to win search placement.",
    status: "PENDING",
  },
  {
    sku: "SKU-3310",
    productName: "Orbit Hydration Serum",
    category: "Beauty",
    currentPrice: 42,
    suggestedPrice: 44.5,
    confidence: 84,
    volumeLift: 4,
    marginDelta: 3.3,
    rationale: "Inventory is constrained and repeat-purchase signals support a measured premium.",
    status: "PENDING",
  },
  {
    sku: "SKU-5067",
    productName: "TerraFlex Training Mat",
    category: "Sports",
    currentPrice: 78,
    suggestedPrice: 74.25,
    confidence: 79,
    volumeLift: 11,
    marginDelta: 0.8,
    rationale: "Clearance pressure is rising across the category; keep the price inside the safe band.",
    status: "PENDING",
  },
];

const competitorSeed = [
  { name: "Your store", price: 148, delta: 0, deltaPct: 0, inStock: true, lastSeen: "Now" },
  { name: "Amazon", price: 154.2, delta: 6.2, deltaPct: 4.2, inStock: true, lastSeen: "18 sec ago" },
  { name: "Walmart", price: 145.5, delta: -2.5, deltaPct: -1.7, inStock: true, lastSeen: "32 sec ago" },
  { name: "Target", price: 150.0, delta: 2, deltaPct: 1.4, inStock: true, lastSeen: "44 sec ago" },
  { name: "eBay", price: 139.9, delta: -8.1, deltaPct: -5.5, inStock: false, lastSeen: "1 min ago" },
];

const activitySeed = [
  { id: "a-1", type: "CRITICAL", title: "Target undercut detected", message: "SKU-9402 is $2.50 above Target; recommendation queued for review.", time: "Just now" },
  { id: "a-2", type: "WARNING", title: "Inventory threshold crossed", message: "SKU-7021 dropped below 50 units in the west warehouse.", time: "2 min ago" },
  { id: "a-3", type: "INFO", title: "Competitor scrape completed", message: "428 marketplace offers refreshed across 31 categories.", time: "4 min ago" },
  { id: "a-4", type: "INFO", title: "Elasticity model refreshed", message: "Demand forecast confidence improved by 1.8% for Electronics.", time: "7 min ago" },
  { id: "a-5", type: "WARNING", title: "Margin guardrail active", message: "SKU-5067 held at the minimum 20% contribution margin.", time: "12 min ago" },
];

const historySeed = Array.from({ length: 24 }, (_, index) => {
  const hour = index - 23;
  const base = 150 + Math.sin(index / 2.8) * 5;
  return {
    time: `${String((24 + hour) % 24).padStart(2, "0")}:00`,
    yourPrice: Number((base + Math.sin(index / 2) * 2).toFixed(2)),
    amazon: Number((base + 5 + Math.cos(index / 3) * 3).toFixed(2)),
    walmart: Number((base - 2 + Math.sin(index / 3) * 2.5).toFixed(2)),
    inventory: Math.max(32, Math.round(122 - index * 2.7 + Math.sin(index) * 9)),
  };
});

const elasticitySeed = Array.from({ length: 13 }, (_, index) => {
  const price = 100 + index * 8;
  const units = Math.max(35, Math.round(286 - index * 10.5 + Math.sin(index / 1.8) * 8));
  return {
    price,
    units,
    profit: Math.round(price * units * (0.2 + Math.min(index, 8) * 0.008)),
  };
});

const rulesSeed = [
  {
    id: "rule-1",
    name: "Competitive match with margin protection",
    enabled: true,
    condition: "Competitor price drops > 5% AND inventory > 50 units",
    action: "Match competitor price",
    outcome: "Maintain minimum 20% margin",
  },
  {
    id: "rule-2",
    name: "Scarcity premium",
    enabled: true,
    condition: "Inventory < 20 units AND demand velocity > 70",
    action: "Increase price by up to 4%",
    outcome: "Protect contribution margin",
  },
  {
    id: "rule-3",
    name: "Clearance guardrail",
    enabled: false,
    condition: "Days of supply > 45 AND velocity < 30",
    action: "Discount by 3%",
    outcome: "Require analyst approval",
  },
];

export const dashboardFallback = {
  metrics: {
    activeSkus: 1248,
    revenueLift: 12.8,
    marginGain: 4.6,
    competitorChanges: 37,
    elasticity: 1.42,
    winRate: 84,
    revenueMultiplier: 1.18,
    projectedRevenue: 184200,
  },
  recommendations: productSeed,
  competitors: competitorSeed,
  activity: activitySeed,
  history: historySeed,
  elasticity: elasticitySeed,
  rules: rulesSeed,
};

export const createDashboardSnapshot = (tick = 0) => {
  const wobble = Math.sin(tick / 2) * 0.6;
  return {
    ...dashboardFallback,
    metrics: {
      ...dashboardFallback.metrics,
      revenueLift: Number((12.8 + wobble).toFixed(1)),
      marginGain: Number((4.6 + wobble / 3).toFixed(1)),
      competitorChanges: dashboardFallback.metrics.competitorChanges + (tick % 4),
      winRate: Math.min(99, Math.round(84 + wobble)),
      projectedRevenue: Math.round(184200 + wobble * 420),
    },
    recommendations: productSeed.map((item, index) => ({
      ...item,
      suggestedPrice: Number((item.suggestedPrice + Math.sin((tick + index) / 2) * 0.35).toFixed(2)),
    })),
  };
};

export const normalizeApiSnapshot = (responses = {}) => {
  const apiMetrics = responses.metrics || {};
  const apiRecommendations = responses.recommendations;
  const fallback = createDashboardSnapshot(0);

  return {
    ...fallback,
    metrics: {
      ...fallback.metrics,
      activeSkus: apiMetrics.liveProducts || apiMetrics.activeSkus || fallback.metrics.activeSkus,
      revenueLift: apiMetrics.revenueLift || apiMetrics.conversionRate || fallback.metrics.revenueLift,
      marginGain: apiMetrics.marginGain || fallback.metrics.marginGain,
      competitorChanges: apiMetrics.competitorChanges || fallback.metrics.competitorChanges,
      elasticity: apiMetrics.elasticity || fallback.metrics.elasticity,
      winRate: apiMetrics.winRate || apiMetrics.pricingAccuracy || fallback.metrics.winRate,
      revenueMultiplier: apiMetrics.revenueMultiplier || fallback.metrics.revenueMultiplier,
      projectedRevenue: apiMetrics.totalRevenue || fallback.metrics.projectedRevenue,
    },
    recommendations: Array.isArray(apiRecommendations) && apiRecommendations.length
      ? apiRecommendations.map((item, index) => ({
          ...fallback.recommendations[index % fallback.recommendations.length],
          ...item,
          sku: item.sku || `SKU-${String(item.id || index + 1).padStart(4, "0")}`,
          productName: item.productName || item.product?.name || fallback.recommendations[index % fallback.recommendations.length].productName,
          currentPrice: Number(item.currentPrice || item.current_price || 0) || fallback.recommendations[index % fallback.recommendations.length].currentPrice,
          suggestedPrice: Number(item.suggestedPrice || item.suggested_price || 0) || fallback.recommendations[index % fallback.recommendations.length].suggestedPrice,
          confidence: Number(item.confidence || item.confidence_score || 0) || fallback.recommendations[index % fallback.recommendations.length].confidence,
          rationale: item.reason || item.rationale || fallback.recommendations[index % fallback.recommendations.length].rationale,
        }))
      : fallback.recommendations,
  };
};

