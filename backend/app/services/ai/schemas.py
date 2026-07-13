from pydantic import BaseModel, Field
from typing import Literal, List


class MarketAnalysisSchema(BaseModel):
    market_position: Literal["leader", "competitive", "lagging"] = Field(
        ..., description="The product's current position in the market"
    )
    avg_competitor_price: float = Field(..., description="Average price across competitors")
    min_competitor_price: float = Field(..., description="Lowest competitor price")
    max_competitor_price: float = Field(..., description="Highest competitor price")
    price_gap_pct: float = Field(..., description="% difference from our price to avg competitor")
    insights: str = Field(..., description="1-2 sentence market insight")
    suggested_adjustment_pct: float = Field(..., description="Suggested adjustment percentage based purely on market")


class DemandAnalysisSchema(BaseModel):
    demand_level: Literal["high", "medium", "low"] = Field(...)
    trend_direction: Literal["rising", "stable", "declining"] = Field(...)
    avg_trend_score: float = Field(...)
    avg_seasonal_factor: float = Field(...)
    avg_velocity: float = Field(...)
    demand_based_price_adjustment_pct: float = Field(...)
    insights: str = Field(...)


class InventoryAnalysisSchema(BaseModel):
    inventory_status: Literal["overstock", "healthy", "low_stock", "out_of_stock"] = Field(...)
    current_margin_pct: float = Field(...)
    min_viable_price: float = Field(...)
    inventory_pressure_adjustment_pct: float = Field(...)
    insights: str = Field(...)


class PricingStrategySchema(BaseModel):
    recommended_price: float = Field(..., description="Final recommended price in INR")
    price_change_pct: float = Field(..., description="Percentage change from current catalog price")
    strategy: Literal["penetration", "competitive", "premium", "clearance", "maintain"] = Field(...)
    rationale: str = Field(..., description="2-3 sentences explaining the recommendation")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    risk_level: Literal["low", "medium", "high"] = Field(...)
    projected_volume_increase_pct: float = Field(...)
    projected_monthly_profit_lift: float = Field(...)


class ComplianceSchema(BaseModel):
    compliant: bool = Field(...)
    margin_at_recommended: float = Field(...)
    margin_floor_met: bool = Field(...)
    violations: List[str] = Field(default_factory=list)
    final_recommended_price: float = Field(...)
    compliance_notes: str = Field(...)
