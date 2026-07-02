MARKET_INTELLIGENCE_SYSTEM = """You are a Market Intelligence Agent for a dynamic pricing system.
Your job is to analyze competitor pricing data and market position.
Return structured JSON analysis only."""

DEMAND_FORECASTING_SYSTEM = """You are a Demand Forecasting Agent for a dynamic pricing system.
Your job is to analyze demand signals, trend scores, seasonal factors, and SKU velocity.
Return structured JSON analysis only."""

INVENTORY_COST_SYSTEM = """You are an Inventory & Cost Analysis Agent.
Your job is to analyze inventory levels and cost structure to inform pricing decisions.
Return structured JSON analysis only."""

PRICING_STRATEGY_SYSTEM = """You are a Pricing Strategy Agent.
Your job is to synthesize all market, demand, and inventory signals to recommend an optimal price.
Return structured JSON analysis only."""

COMPLIANCE_SYSTEM = """You are an Execution & Compliance Agent.
Your job is to validate that a recommended price complies with margin floors, rules, and business constraints.
Return structured JSON analysis only."""


def market_intelligence_prompt(product: dict, competitor_prices: list) -> str:
    return f"""Analyze the market position for this product:

Product: {product['name']} (SKU: {product['sku']})
Current Price: ${product['current_price']}
Cost Price: ${product['cost_price']}

Competitor Prices:
{competitor_prices}

Return JSON with keys:
- market_position: "leader"|"competitive"|"lagging"
- avg_competitor_price: float
- min_competitor_price: float
- max_competitor_price: float
- price_gap_pct: float (% diff from our price to avg competitor)
- insights: string (1-2 sentence insight)
- suggested_adjustment_pct: float (how much to adjust in %)"""


def demand_forecasting_prompt(product: dict, demand_signals: list) -> str:
    return f"""Analyze demand signals for pricing:

Product: {product['name']} (SKU: {product['sku']})
Current Price: ${product['current_price']}

Demand Signals (most recent):
{demand_signals}

Return JSON with keys:
- demand_level: "high"|"medium"|"low"
- trend_direction: "rising"|"stable"|"declining"
- avg_trend_score: float
- avg_seasonal_factor: float
- avg_velocity: float
- demand_based_price_adjustment_pct: float
- insights: string"""


def inventory_cost_prompt(product: dict) -> str:
    return f"""Analyze inventory and cost structure:

Product: {product['name']} (SKU: {product['sku']})
Current Price: ${product['current_price']}
Cost Price: ${product['cost_price']}
Inventory Count: {product['inventory_count']}
Current Margin: {product.get('margin', 0):.2%}

Return JSON with keys:
- inventory_status: "overstock"|"healthy"|"low_stock"|"out_of_stock"
- current_margin_pct: float
- min_viable_price: float
- inventory_pressure_adjustment_pct: float (negative to clear stock, positive to preserve for low stock)
- insights: string"""


def pricing_strategy_prompt(
    product: dict,
    market_analysis: dict,
    demand_analysis: dict,
    inventory_analysis: dict,
    pricing_rules: dict,
) -> str:
    return f"""Synthesize all signals to recommend an optimal price:

Product: {product['name']} (SKU: {product['sku']})
Current Price: ${product['current_price']}
Cost Price: ${product['cost_price']}

Market Analysis: {market_analysis}
Demand Analysis: {demand_analysis}
Inventory Analysis: {inventory_analysis}

Pricing Rules:
- Minimum Margin: {pricing_rules.get('minimum_margin', 0.1):.2%}
- Auto-execute Threshold: {pricing_rules.get('auto_execute_threshold', 0.95):.2%}

Return JSON with keys:
- recommended_price: float
- price_change_pct: float
- strategy: "penetration"|"competitive"|"premium"|"clearance"|"maintain"
- rationale: string (2-3 sentences explaining the recommendation)
- confidence_score: float (0.0 to 1.0)
- risk_level: "low"|"medium"|"high"
- projected_volume_increase_pct: float (predicted increase in sales volume)
- projected_monthly_profit_lift: float (predicted extra profit in dollars) """


def compliance_prompt(
    product: dict, recommended_price: float, pricing_rules: dict
) -> str:
    return f"""Validate this price recommendation for compliance:

Product: {product['name']}
Cost Price: ${product['cost_price']}
Current Price: ${product['current_price']}
Recommended Price: ${recommended_price}
Minimum Margin Rule: {pricing_rules.get('minimum_margin', 0.1):.2%}

Return JSON with keys:
- compliant: boolean
- margin_at_recommended: float
- margin_floor_met: boolean
- violations: list of strings (empty if compliant)
- final_recommended_price: float (adjusted if needed to meet compliance)
- compliance_notes: string"""