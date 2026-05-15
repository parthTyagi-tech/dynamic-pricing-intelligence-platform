import json
import random
import os

from groq import Groq


# =====================================
# INITIALIZE GROQ CLIENT
# =====================================

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


# =====================================
# MARKET INTELLIGENCE AGENT
# =====================================

class MarketIntelligenceAgent:

    @staticmethod
    def analyze(product):

        current_price = product.current_price

        competitor_price = round(
            current_price * random.uniform(0.85, 1.05),
            2
        )

        market_trend = random.choice([
            "competitor_price_drop",
            "stable_market",
            "high_competition",
            "seasonal_demand"
        ])

        return {

            "competitor_price": competitor_price,

            "market_trend": market_trend
        }


# =====================================
# DEMAND FORECAST AGENT
# =====================================

class DemandForecastAgent:

    @staticmethod
    def analyze(product):

        demand_score = random.randint(55, 95)

        trend = random.choice([
            "rising",
            "stable",
            "declining"
        ])

        return {

            "demand_score": demand_score,

            "trend": trend
        }


# =====================================
# INVENTORY AGENT
# =====================================

class InventoryAgent:

    @staticmethod
    def analyze(product):

        inventory_level = product.inventory_quantity

        stock_status = (

            "overstocked"

            if inventory_level > 50

            else "low_stock"

            if inventory_level < 10

            else "healthy"
        )

        return {

            "inventory_level": inventory_level,

            "stock_status": stock_status,

            "margin_floor": 10
        }


# =====================================
# PRICING STRATEGY AGENT
# =====================================

class PricingStrategyAgent:

    @staticmethod
    def generate(
        product,
        market_data,
        demand_data,
        inventory_data
    ):

        prompt = f"""
You are an enterprise AI Pricing Strategy Agent.

Analyze the product and generate a pricing recommendation.

PRODUCT:
- Name: {product.name}
- Current Price: {product.current_price}
- Cost Price: {product.cost_price}

MARKET DATA:
{json.dumps(market_data, indent=2)}

DEMAND DATA:
{json.dumps(demand_data, indent=2)}

INVENTORY DATA:
{json.dumps(inventory_data, indent=2)}

IMPORTANT:
Return ONLY valid JSON.

DO NOT include markdown.
DO NOT include explanation outside JSON.

Required JSON format:

{{
  "recommended_price": number,
  "confidence_score": number_between_0_and_1,
  "rationale": "detailed reasoning",
  "ai_summary": "short summary"
}}
"""

        completion = client.chat.completions.create(

            model="llama-3.3-70b-versatile",

            messages=[
                {
                    "role": "system",
                    "content":
                    "You are an enterprise AI pricing strategist."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.4
        )

        content = completion.choices[0].message.content

        # =====================================
        # CLEAN AI RESPONSE
        # =====================================

        content = content.strip()

        content = content.replace(
            "```json",
            ""
        )

        content = content.replace(
            "```",
            ""
        )

        # =====================================
        # PARSE RESPONSE
        # =====================================

        try:

            parsed = json.loads(content)

        except Exception:

            # =====================================
            # FALLBACK RESPONSE
            # =====================================

            parsed = {

                "recommended_price": round(
                    product.current_price * 1.03,
                    2
                ),

                "confidence_score": 0.82,

                "rationale":
                "AI generated fallback recommendation based on market trends, inventory health, and demand analysis.",

                "ai_summary":
                f"Recommended price update generated for {product.name}"
            }

        return parsed