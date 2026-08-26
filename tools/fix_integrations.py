from pathlib import Path

path = Path('/home/ubuntu/dynamic-pricing-intelligence-platform/backend/app/routes/startup_routes.py')
s = path.read_text()
s = s.replace('INTEGRATIONS_STORE = {}', 'SUPPORTED_INTEGRATIONS = {"shopify", "woocommerce", "amazon"}')
start = s.index('@startup_bp.route("/integrations"')
replacement = '''@startup_bp.route("/integrations", methods=["GET", "POST"])
@jwt_required()
def handle_integrations():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    organization = current_user.organization
    if not organization:
        return {"success": False, "message": "Organization not found"}, 404

    if request.method == "POST":
        data = request.get_json() or {}
        platform = str(data.get("platform", "")).strip().lower()
        connected = bool(data.get("connected", False))
        store_url = str(data.get("store_url", "")).strip()
        if platform not in SUPPORTED_INTEGRATIONS:
            return {"success": False, "message": f"Platform '{platform}' is not supported"}, 400
        if connected and not store_url:
            return {"success": False, "message": "store_url is required when connecting an integration"}, 400
        organization.store_platform = platform if connected else None
        organization.store_domain = store_url if connected else None
        db.session.commit()

    current_platform = organization.store_platform
    current_domain = organization.store_domain
    integrations = {
        platform: {
            "connected": platform == current_platform and bool(current_domain),
            "store_url": current_domain if platform == current_platform else "",
            "api_version": "",
            "last_sync": None,
        }
        for platform in sorted(SUPPORTED_INTEGRATIONS)
    }
    return {"success": True, "integrations": integrations, "webhook_logs": []}, 200
'''
path.write_text(s[:start] + replacement + '\n')
