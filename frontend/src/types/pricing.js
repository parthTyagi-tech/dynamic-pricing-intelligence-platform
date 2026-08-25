/**
 * Pricing intelligence domain contracts.
 *
 * The repository currently ships as JSX, so these JSDoc interfaces provide
 * explicit contracts without forcing a migration of the existing application.
 */

/** @typedef {{ sku: string, productName: string, category: string, currentPrice: number, suggestedPrice: number, confidence: number, volumeLift: number, marginDelta: number, rationale: string, status: 'PENDING'|'APPROVED'|'REJECTED' }} ProductSKU */
/** @typedef {{ name: string, price: number, delta: number, deltaPct: number, inStock: boolean, lastSeen: string }} CompetitorPrice */
/** @typedef {{ id: string|number, type: 'CRITICAL'|'WARNING'|'INFO', title: string, message: string, time: string }} PriceChangeLog */
/** @typedef {{ price: number, units: number, profit: number }} ElasticityPoint */
/** @typedef {{ id: string, name: string, enabled: boolean, condition: string, action: string, outcome: string }} PricingRule */

export const pricingTypes = {
  ProductSKU: 'ProductSKU',
  CompetitorPrice: 'CompetitorPrice',
  PriceChangeLog: 'PriceChangeLog',
  ElasticityPoint: 'ElasticityPoint',
  PricingRule: 'PricingRule',
};
