from pathlib import Path

root = Path('/home/ubuntu/dynamic-pricing-intelligence-platform')

dashboard = root / 'backend/app/routes/dashboard_routes.py'
s = dashboard.read_text()
s = s.replace('import random\n', '')
start = s.index('# =====================================\n# LIVE TICK SIMULATOR HELPER')
end = s.index('# =====================================\n# DASHBOARD ANALYTICS', start)
s = s[:start] + s[end:]
s = s.replace('    # Run live simulation tick\n    simulate_live_tick(current_user.organization_id)\n\n', '')
s = s.replace('    # Apply minor live wiggles (jitter) to simulate active shifts\n    wiggle = lambda val: round(val * random.uniform(0.985, 1.015), 2)\n\n', '')
s = s.replace('    # Apply minor live wiggles (jitter) to simulate active price movements\n    wiggle = lambda val: round(val * random.uniform(0.98, 1.02), 2)\n\n', '')
s = s.replace('    wiggle = lambda val: round(min(max(val * random.uniform(0.97, 1.03), 0.0), 100.0), 1)\n\n', '')
s = s.replace('    wiggle = lambda val: round(min(max(val * random.uniform(0.985, 1.015), 30.0), 100.0), 1)\n\n', '')
s = s.replace('"actual": wiggle(base_actual * 0.7)', '"actual": round(base_actual * 0.7, 2)')
s = s.replace('"predicted": wiggle(base_actual * 0.75)', '"predicted": round(base_actual * 0.75, 2)')
s = s.replace('"actual": wiggle(base_actual * 0.85)', '"actual": round(base_actual * 0.85, 2)')
s = s.replace('"predicted": wiggle(base_actual * 0.95)', '"predicted": round(base_actual * 0.95, 2)')
s = s.replace('"actual": wiggle(base_actual * 1.0)', '"actual": round(base_actual * 1.0, 2)')
s = s.replace('"predicted": wiggle(base_actual * 1.08)', '"predicted": round(base_actual * 1.08, 2)')
s = s.replace('"actual": wiggle(base_actual * 1.25)', '"actual": round(base_actual * 1.25, 2)')
s = s.replace('"predicted": wiggle(base_actual * 1.30)', '"predicted": round(base_actual * 1.30, 2)')
s = s.replace('"aiPrice": wiggle(avg_our_price * 0.95)', '"aiPrice": round(avg_our_price * 0.95, 2)')
s = s.replace('"competitorPrice": wiggle(avg_comp_price * 0.94)', '"competitorPrice": round(avg_comp_price * 0.94, 2)')
s = s.replace('"marketAverage": wiggle((avg_our_price + avg_comp_price) * 0.47)', '"marketAverage": round((avg_our_price + avg_comp_price) * 0.47, 2)')
s = s.replace('"aiPrice": wiggle(avg_our_price * 1.0)', '"aiPrice": round(avg_our_price * 1.0, 2)')
s = s.replace('"competitorPrice": wiggle(avg_comp_price * 0.99)', '"competitorPrice": round(avg_comp_price * 0.99, 2)')
s = s.replace('"marketAverage": wiggle((avg_our_price + avg_comp_price) * 0.495)', '"marketAverage": round((avg_our_price + avg_comp_price) * 0.495, 2)')
s = s.replace('"aiPrice": wiggle(avg_our_price * 1.05)', '"aiPrice": round(avg_our_price * 1.05, 2)')
s = s.replace('"competitorPrice": wiggle(avg_comp_price * 1.02)', '"competitorPrice": round(avg_comp_price * 1.02, 2)')
s = s.replace('"marketAverage": wiggle((avg_our_price + avg_comp_price) * 0.51)', '"marketAverage": round((avg_our_price + avg_comp_price) * 0.51, 2)')
s = s.replace('"demand": wiggle(float(score) * 100) if score is not None else 50.0', '"demand": round(float(score) * 100, 1) if score is not None else 0.0')
# Empty DB means empty response, not fabricated demand/category data.
old = '''    else:\n        # Fallback to product category distribution counts\n        cat_counts = db.session.query(\n            Product.category,\n            func.count(Product.id)\n        ).filter(\n            Product.organization_id == current_user.organization_id\n        ).group_by(\n            Product.category\n        ).all()\n\n        if cat_counts:\n            total_cnt = sum(c[1] for c in cat_counts)\n            return [\n                {\n                    "category": cat or "General",\n                    "demand": wiggle((count / total_cnt) * 100)\n                }\n                for cat, count in cat_counts\n            ], 200\n\n        return [], 200\n'''
s = s.replace(old, '    return [], 200\n')
s = s.replace('avg_conf = sum(r.confidence_score for r in recs) / len(recs) if recs else 0.95', 'avg_conf = sum(r.confidence_score for r in recs) / len(recs) if recs else 0.0')
s = s.replace('avg_margin = sum(p.calculate_margin() for p in products) / len(products) if products else 15.0', 'avg_margin = sum(p.calculate_margin() for p in products) / len(products) if products else 0.0')
s = s.replace('conv_rate = (approved / total * 100) if total > 0 else 85.0', 'conv_rate = (approved / total * 100) if total > 0 else 0.0')
s = s.replace('"score": wiggle(avg_conf)', '"score": round(min(max(avg_conf, 0.0), 100.0), 1)')
s = s.replace('"score": wiggle(min(max(avg_conf - 3.0, 60.0), 99.0))', '"score": round(min(max(avg_conf - 3.0, 0.0), 100.0), 1)')
s = s.replace('"score": wiggle(opt_score)', '"score": round(min(max(opt_score, 0.0), 100.0), 1)')
s = s.replace('"score": wiggle(min(max(conv_rate + 10.0, 70.0), 99.0))', '"score": round(min(max(conv_rate + 10.0, 0.0), 100.0), 1)')
s = s.replace('opt_score = min(max(50.0 + avg_margin * 2.0, 60.0), 99.0)', 'opt_score = min(max(avg_margin * 2.0, 0.0), 100.0)')
s = s.replace('"activeModelsCount": 5 # Compliance, Demand, Inventory, Market, Pricing Strategy', '"activeModelsCount": PricingRecommendation.query.filter_by(organization_id=current_user.organization_id).with_entities(PricingRecommendation.agent_analysis).count()')
dashboard.write_text(s)

rec = root / 'backend/app/routes/recommendation_routes.py'
s = rec.read_text()
s = s.replace('import random\n', '')
s = s.replace('''        demand_signal = DemandSignal(\n            trend_score=demand_data["demand_score"] / 100,\n            seasonal_factor=1.1,\n            sku_velocity=random.uniform(10, 100),\n            product_id=product.id,\n            organization_id=product.organization_id\n        )\n''', '''        latest_sales = db.session.query(db.func.coalesce(db.func.sum(Sale.quantity), 0)).filter(\n            Sale.product_id == product.id,\n            Sale.organization_id == product.organization_id,\n            Sale.timestamp >= datetime.now(timezone.utc) - timedelta(days=14)\n        ).scalar() or 0\n        demand_signal = DemandSignal(\n            trend_score=demand_data["demand_score"] / 100,\n            seasonal_factor=demand_data.get("seasonal_factor", 1.0),\n            sku_velocity=float(latest_sales) / 14.0,\n            product_id=product.id,\n            organization_id=product.organization_id\n        )\n''')
if 'from app.models.market_data import' in s and 'Sale' not in s.split('from app.models.market_data import',1)[1].split('\n',1)[0]:
    s = s.replace('from app.models.market_data import CompetitorPrice, DemandSignal', 'from app.models.market_data import CompetitorPrice, DemandSignal, Sale')
rec.write_text(s)

startup = root / 'backend/app/routes/startup_routes.py'
s = startup.read_text()
s = s.replace('import random\n', 'import os\n')
# Never expose a process-local fake integration store; return an explicit empty state until persisted integration models exist.
start = s.index('# In-memory storage for mock integrations configurations')
end = s.index('\n\n@startup_bp.route("/matcher"', start)
s = s[:start] + 'INTEGRATIONS_STORE = {}' + s[end:]
s = s.replace('''    if platform not in INTEGRATIONS_STORE:\n            return {"success": False, "message": f"Platform \'{platform}\' is not supported"}, 400\n\n        INTEGRATIONS_STORE[platform]["connected"] = connected\n''', '''    if platform not in {"shopify", "woocommerce", "amazon"}:\n            return {"success": False, "message": f"Platform \'{platform}\' is not supported"}, 400\n        INTEGRATIONS_STORE.setdefault(platform, {"connected": False, "store_url": "", "api_version": "", "last_sync": None})\n        INTEGRATIONS_STORE[platform]["connected"] = connected\n''')
# Stop returning hard-coded billing and webhook history; those require persisted billing/webhook models.
s = s.replace('''    # Calculate dynamic mock invoice values based on actual DB product counts\n''', '    # Billing data is unavailable until a persisted billing provider is configured.\n')
s = s.replace('''    revenue_lift = float(product_count * 1420.00) if product_count > 0 else 45210.00\n''', '''    revenue_lift = 0.0\n''')
s = s.replace('''        "subscription": {\n            "tier": "Pro Growth Plan",\n            "price_monthly": plan_fee,\n            "billing_cycle": "Monthly",\n            "next_billing_date": "2026-07-28"\n        },\n''', '''        "subscription": {\n            "tier": None,\n            "price_monthly": 0.0,\n            "billing_cycle": None,\n            "next_billing_date": None\n        },\n''')
s = s.replace('''            "subscription_due": plan_fee,\n            "total_invoice_due": total_due\n        },\n        "billing_history": [\n            {"invoice_id": "INV-2026-06", "date": "2026-06-28", "amount": 349.50, "status": "paid"},\n            {"invoice_id": "INV-2026-05", "date": "2026-05-28", "amount": 298.12, "status": "paid"},\n            {"invoice_id": "INV-2026-04", "date": "2026-04-28", "amount": 149.00, "status": "paid"}\n        ]\n''', '''            "subscription_due": 0.0,\n            "total_invoice_due": 0.0\n        },\n        "billing_history": []\n''')
# remove hardcoded webhook log block, retain empty persisted state until a webhook model exists.
start = s.index('    # GET returns current status and mock webhook logs list')
end = s.index('\n    return {', start)
s = s[:start] + '    webhook_logs = []\n' + s[end:]
startup.write_text(s)
