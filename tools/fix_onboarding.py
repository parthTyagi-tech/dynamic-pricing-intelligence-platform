from pathlib import Path

path = Path('/home/ubuntu/dynamic-pricing-intelligence-platform/backend/app/routes/auth_routes.py')
s = path.read_text()
start = s.index('# =====================================\n# CONNECT STORE INTEGRATION & SEED CATALOG')
replacement = '''# =====================================
# CONNECT STORE INTEGRATION
# =====================================
@auth_bp.route("/connect-integration", methods=["POST"])
@jwt_required()
def connect_integration():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return {"success": False, "message": "User not found"}, 404

    org = user.organization
    if not org:
        return {"success": False, "message": "Organization not found"}, 404

    data = request.get_json() or {}
    platform = str(data.get("platform", "")).strip().lower()
    domain = str(data.get("domain", "")).strip()
    if platform not in {"shopify", "woocommerce", "amazon"}:
        return {"success": False, "message": "Supported platforms are shopify, woocommerce, and amazon"}, 400
    if not domain or len(domain) > 255 or any(char.isspace() for char in domain):
        return {"success": False, "message": "A valid store domain is required"}, 400

    # Store metadata is persisted for the authenticated organization. Catalog data
    # must come from the CSV importer or a verified provider adapter; this route
    # intentionally never invents products, prices, demand, or competitor records.
    org.store_platform = platform
    org.store_domain = domain
    db.session.commit()

    return {
        "success": True,
        "message": f"{platform.capitalize()} connection saved. Import or sync the verified catalog to continue.",
        "user": user.to_dict(),
        "catalog_count": Product.query.filter_by(organization_id=org.id).count(),
    }, 200
'''
path.write_text(s[:start] + replacement + '\n')
