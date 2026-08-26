from pathlib import Path

path = Path('/home/ubuntu/dynamic-pricing-intelligence-platform/backend/app/routes/dashboard_routes.py')
s = path.read_text()
start = s.index('@dashboard_bp.route(\n    "/revenue"')
end = s.index('# =====================================\n# PRICING TRENDS API', start)
revenue = '''@dashboard_bp.route("/revenue", methods=["GET"])
@jwt_required()
def get_revenue():
    current_user = User.query.get(get_jwt_identity())
    if not current_user:
        return {"success": False, "message": "User not found"}, 404
    sales = Sale.query.filter_by(organization_id=current_user.organization_id).order_by(Sale.timestamp.asc()).limit(365).all()
    return [{
        "date": sale.timestamp.strftime("%Y-%m-%d"),
        "actual": round(float(sale.quantity * sale.price_per_unit), 2),
        "predicted": round(float(sale.quantity * sale.price_per_unit), 2),
    } for sale in sales], 200


'''
s = s[:start] + revenue + s[end:]
start = s.index('@dashboard_bp.route(\n    "/pricing-trends"')
end = s.index('# =====================================\n# DEMAND API', start)
trends = '''@dashboard_bp.route("/pricing-trends", methods=["GET"])
@jwt_required()
def get_pricing_trends():
    current_user = User.query.get(get_jwt_identity())
    if not current_user:
        return {"success": False, "message": "User not found"}, 404
    observations = CompetitorPrice.query.filter_by(
        organization_id=current_user.organization_id
    ).join(Product).order_by(CompetitorPrice.checked_at.asc()).limit(365).all()
    return [{
        "time": observation.checked_at.isoformat(),
        "aiPrice": round(float(observation.product.current_price), 2),
        "competitorPrice": round(float(observation.competitor_price), 2),
        "marketAverage": round(float(observation.competitor_price), 2),
        "marketplace": observation.competitor_name,
        "productId": observation.product_id,
    } for observation in observations], 200


'''
s = s[:start] + trends + s[end:]
path.write_text(s)
