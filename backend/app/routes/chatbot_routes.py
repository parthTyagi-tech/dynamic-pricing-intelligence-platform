import random
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.product import Product, RecommendationStatus
from app.models.market_data import CompetitorPrice, DemandSignal
from app.models.recommendation import PricingRecommendation, ApprovalAction, ApprovalActionType
from app.services.ai_pricing_service import (
    MarketIntelligenceAgent,
    DemandForecastAgent,
    InventoryAgent,
    PricingStrategyAgent
)
from app.services.ai.client import chat_completion

chatbot_bp = Blueprint("chatbot", __name__)


def _trigger_agent_analysis(product, current_user):
    """Executes the full 5-agent pricing workflow for a product and saves it to DB."""
    # Execute the entire 5-agent pipeline concurrently in parallel!
    ai_result = PricingStrategyAgent.generate(product)

    market_data = ai_result["agent_analysis"]["market_agent"]
    demand_data = ai_result["agent_analysis"]["demand_agent"]
    inventory_data = ai_result["agent_analysis"]["inventory_agent"]

    # Save mock logs for verification
    competitor_data = CompetitorPrice(
        competitor_name="AI Market Agent",
        competitor_price=market_data["competitor_price"],
        product_id=product.id,
        organization_id=current_user.organization_id
    )
    db.session.add(competitor_data)

    demand_signal = DemandSignal(
        trend_score=demand_data["demand_score"] / 100,
        seasonal_factor=1.1,
        sku_velocity=random.uniform(10, 100),
        product_id=product.id,
        organization_id=current_user.organization_id
    )
    db.session.add(demand_signal)

    # Determine status & approval actions
    execution_route = ai_result.get("execution_route", "human_review")
    
    recommendation = PricingRecommendation(
        product_id=product.id,
        recommended_price=ai_result["recommended_price"],
        confidence_score=ai_result["confidence_score"] / 100.0 if ai_result["confidence_score"] > 1.0 else ai_result["confidence_score"],
        rationale=ai_result["rationale"],
        ai_summary=ai_result["ai_summary"],
        created_by_agent="PricingStrategyAgent",
        agent_analysis={
            "market_agent": market_data,
            "demand_agent": demand_data,
            "inventory_agent": inventory_data,
            "compliance_agent": ai_result.get("compliance", {})
        },
        organization_id=current_user.organization_id
    )
    db.session.add(recommendation)
    db.session.flush()

    if execution_route == "auto_execute":
        recommendation.status = RecommendationStatus.EXECUTED
        previous_price = product.current_price
        product.current_price = ai_result["recommended_price"]
        product.recommendation_status = RecommendationStatus.APPROVED

        action = ApprovalAction(
            recommendation_id=recommendation.id,
            action_type=ApprovalActionType.AUTO_EXECUTE,
            previous_price=previous_price,
            executed_price=ai_result["recommended_price"],
            approved_by=None  # System auto-executed
        )
        db.session.add(action)
    else:
        recommendation.status = RecommendationStatus.PENDING
        product.recommendation_status = RecommendationStatus.PENDING

    db.session.commit()

    return recommendation, ai_result


@chatbot_bp.route("/chat", methods=["POST"])
@jwt_required()
def chat():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return {"success": False, "message": "Message is required"}, 400

    msg_lower = message.lower()

    # =========================================================================
    # COMMAND ROUTING (Orchestrator Logic)
    # =========================================================================

    # 1. Trigger agentic workflow (Analyse / Run Strategy)
    if any(msg_lower.startswith(keyword) for keyword in ["analyse", "analyze", "run strategy", "run pricing"]):
        # Extract product name or SKU
        product_name = message
        for phrase in ["analyse", "analyze", "run strategy for", "run pricing for"]:
            if phrase in msg_lower:
                product_name = message[msg_lower.find(phrase) + len(phrase):].strip()
                break

        product_name = product_name.replace("product", "").strip()

        # Query database for product
        product = Product.query.filter(
            Product.organization_id == current_user.organization_id,
            (Product.sku.ilike(f"%{product_name}%")) | (Product.name.ilike(f"%{product_name}%"))
        ).first()

        if not product:
            return {
                "success": True,
                "response": f"⚠️ Could not find a product matching '**{product_name}**' in your catalog. Please check the SKU or product name and try again."
            }, 200

        try:
            rec, ai_res = _trigger_agent_analysis(product, current_user)
            comp_res = ai_res.get("compliance", {})
            route_str = "**Auto-Executed** (confidence exceeds compliance threshold)" if rec.status == RecommendationStatus.EXECUTED else "**Queued for Review**"

            response_markdown = f"""
### 🧠 Multi-Agent Pricing Execution Completed for *{product.name}*
All 5 specialized agents have executed their analysis sequence. The recommendation has been generated and is {route_str}.

#### 📊 Agent Consensus breakdown:
- 🌐 **Market Intelligence Agent**: Competitor average price is **${rec.agent_analysis['market_agent']['competitor_price']:.2f}** (our current price: **${product.current_price:.2f}**).
- 📉 **Demand Forecast Agent**: Category trend is **{rec.agent_analysis['demand_agent']['trend']}** (Demand Score: **{rec.agent_analysis['demand_agent']['demand_score']}**).
- 📦 **Inventory & Cost Agent**: Stock is **{rec.agent_analysis['inventory_agent']['stock_status']}** (Inventory quantity: **{product.inventory_quantity}**).
- ⚙️ **Execution & Compliance Agent**: Minimum margin checks returned **{'COMPLIANT' if comp_res.get('compliant', True) else 'VIOLATION ADJUSTED'}** (Margin at suggested price: **{comp_res.get('margin_at_recommended', 0.0):.1f}%**).

#### 🎯 Recommendation Output:
- **Current Price**: `${product.current_price:.2f}`
- **Suggested Price**: `${rec.recommended_price:.2f}`
- **Pricing Strategy**: `{ai_res['strategy'].upper()}`
- **Confidence Score**: `{int(rec.confidence_score * 100)}%`
- **Rationale**: {rec.rationale}

[View approvals panel to execute this price update](/approvals)
"""
            return {"success": True, "response": response_markdown.strip()}, 200

        except Exception as e:
            db.session.rollback()
            return {
                "success": True,
                "response": f"❌ An error occurred during multi-agent pricing orchestration: {str(e)}"
            }, 200

    # 2. View Product Details (Price / Details of)
    elif any(msg_lower.startswith(keyword) for keyword in ["price of", "details of", "view product"]):
        product_name = message
        for phrase in ["price of", "details of", "view product"]:
            if phrase in msg_lower:
                product_name = message[msg_lower.find(phrase) + len(phrase):].strip()
                break

        product = Product.query.filter(
            Product.organization_id == current_user.organization_id,
            (Product.sku.ilike(f"%{product_name}%")) | (Product.name.ilike(f"%{product_name}%"))
        ).first()

        if not product:
            return {
                "success": True,
                "response": f"⚠️ Product '**{product_name}**' not found. Ensure the spelling matches your products list."
            }, 200

        margin = product.calculate_margin()
        stock_status = "🔴 Low Stock" if product.is_low_stock() else ("🟡 Overstocked" if product.is_overstocked() else "🟢 Healthy")

        response_markdown = f"""
### 📦 Product Information: {product.name}
- **SKU**: `{product.sku}`
- **Category**: `{product.category}`
- **Description**: {product.description or 'No description provided.'}
- **Current Storefront Price**: `${product.current_price:.2f}`
- **Cost price (COGS)**: `${product.cost_price:.2f}`
- **Gross Profit Margin**: `{margin}%`
- **Minimum Target Margin**: `{product.min_margin_percentage}%`
- **Inventory Count**: `{product.inventory_quantity}` units ({stock_status})
- **Active Rec Status**: `{product.recommendation_status.upper()}`
"""
        return {"success": True, "response": response_markdown.strip()}, 200

    # 3. List Products Catalog Summary
    elif any(msg_lower.startswith(keyword) for keyword in ["list products", "show products", "view catalog"]):
        products = Product.query.filter_by(organization_id=current_user.organization_id).limit(10).all()
        if not products:
            return {"success": True, "response": "Your product catalog is empty. You can add products in the catalog page."}, 200

        rows = []
        for p in products:
            rows.append(f"| `{p.sku}` | {p.name} | `${p.current_price:.2f}` | `{p.inventory_quantity}` | `{p.calculate_margin()}%` |")

        table_body = "\n".join(rows)
        response_markdown = f"""
### 📋 Catalog Summary (Top 10 Products)
Here is an overview of products currently active in your dashboard database:

| SKU | Product Name | Price | Stock | Margin |
|---|---|---|---|---|
{table_body}

*Navigate to the [Products Catalog](/products) to view or manage all items.*
"""
        return {"success": True, "response": response_markdown.strip()}, 200

    # 4. List recommendations
    elif any(msg_lower.startswith(keyword) for keyword in ["list recommendations", "show recommendations", "view approvals"]):
        recs = PricingRecommendation.query.filter_by(
            organization_id=current_user.organization_id,
            status=RecommendationStatus.PENDING
        ).limit(10).all()

        if not recs:
            return {"success": True, "response": "There are no pending recommendations in your approval queue. All recommendations are up-to-date!"}, 200

        rows = []
        for r in recs:
            rows.append(f"| `{r.product.sku}` | {r.product.name} | `${r.product.current_price:.2f}` | `${r.recommended_price:.2f}` | `{int(r.confidence_score * 100)}%` |")

        table_body = "\n".join(rows)
        response_markdown = f"""
### ⏳ Pending Recommendations Queue
Here are the recommendations currently awaiting review:

| SKU | Product | Current Price | Recommended | Confidence |
|---|---|---|---|---|
{table_body}

*Open the [Approvals Panel](/approvals) to execute or modify these changes.*
"""
        return {"success": True, "response": response_markdown.strip()}, 200

    # 5. Help Commands Guide
    elif msg_lower == "help" or msg_lower.startswith("help"):
        help_markdown = """
### 🤖 Klypup AI Coordinator Help Guide
I am Klypup AI, the supervisor coordinating your pricing agents (Market, Demand, Inventory, Strategy, and Compliance). I can run queries and execute recommendations in real-time.

Here are the commands you can use in our chat:
1. 🧠 **Trigger Multi-Agent Strategy**:
   - `analyse [Product Name]` or `run pricing for [SKU]`
   - Runs the full 5-agent AI workflow to recommend a price and logs the consensus.
2. 📦 **Check Product Specifications**:
   - `price of [Product Name]` or `details of [SKU]`
   - Checks margins, costs, and inventory status.
3. 📋 **Inspect Catalog Summary**:
   - `list products`
   - Returns a markdown summary of your product line.
4. ⏳ **Inspect Recommendations**:
   - `list recommendations`
   - Displays all pricing updates awaiting human approval.
"""
        return {"success": True, "response": help_markdown.strip()}, 200

    # =========================================================================
    # CONVERSATIONAL LLM ROUTING
    # =========================================================================
    # Query database statistics to provide LLM context
    products_count = Product.query.filter_by(organization_id=current_user.organization_id).count()
    recs_count = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id, status=RecommendationStatus.PENDING
    ).count()

    system_prompt = f"""You are Klypup AI, the enterprise pricing coordinator and supervisor of all specialized agents.
You have access to real-time information:
- Current user name: {current_user.name}
- Organization: {current_user.organization.name if current_user.organization else 'Acme Pricing'}
- Total products in catalog: {products_count}
- Pending recommendations awaiting review: {recs_count}

Explain pricing trends, answer catalog questions, and direct the user to trigger agent workflows.
Be concise and professional. Use markdown formatting.
If the user asks you to analyze a product, instruct them to say 'analyse [product name]' so you can trigger the real-time agent pipeline.
"""
    # Call unified LLM completion
    response_text = chat_completion(system_prompt=system_prompt, user_prompt=message)

    if not response_text:
        # Conversation Offline mode fallback
        response_text = f"""
Hello **{current_user.name}**! I am Klypup AI, your pricing supervisor. 

Currently, no external AI API credentials (like Groq or OpenAI) are configured in this environment, so I am running in local supervisor command mode.

I can still help you execute workflows. Try asking me:
- "analyse Premium Wireless Headphones" to run the 5 pricing agents.
- "price of Ergonomic Office Chair" to retrieve margins and costs.
- "list products" to print the active catalog.
- "list recommendations" to review the approval queue.
- "help" to review all commands.
"""

    return {"success": True, "response": response_text.strip()}, 200
