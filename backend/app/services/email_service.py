import html
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

EMAILS_DIR = Path(__file__).resolve().parents[2] / "emails"
BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
DEFAULT_SENDER = {"name": "Klypup Pricing Intelligence", "email": "notifications@klypup.ai"}


def _archive_email(subject: str, html_content: str) -> None:
    if os.environ.get("EMAIL_LOCAL_ARCHIVE", "0").lower() not in {"1", "true", "yes"}:
        return
    EMAILS_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in subject if c.isalnum() or c in (" ", "-", "_"))[:100].rstrip()
    path = EMAILS_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{safe}.html"
    path.write_text(html_content, encoding="utf-8")


def _send_or_archive_email(to_email: str, subject: str, html_content: str) -> dict[str, Any]:
    """Send through Brevo when configured; otherwise preserve a deterministic local fallback."""
    _archive_email(subject, html_content)
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if not api_key:
        return {"sent": False, "status": "mocked", "provider": "local_archive"}

    sender = {
        "name": os.environ.get("BREVO_SENDER_NAME", DEFAULT_SENDER["name"]),
        "email": os.environ.get("BREVO_SENDER_EMAIL", DEFAULT_SENDER["email"]),
    }
    try:
        response = requests.post(
            BREVO_ENDPOINT,
            headers={"accept": "application/json", "api-key": api_key, "content-type": "application/json"},
            json={"sender": sender, "to": [{"email": to_email}], "subject": subject, "htmlContent": html_content},
            timeout=15,
        )
        body = response.json() if response.content else {}
        if response.status_code == 201:
            return {"sent": True, "status": "sent", "provider": "brevo", "provider_message_id": body.get("messageId"), "http_status": 201}
        return {"sent": False, "status": "failed", "provider": "brevo", "http_status": response.status_code, "error": body.get("message", response.text[:300])}
    except requests.RequestException as exc:
        return {"sent": False, "status": "failed", "provider": "brevo", "error": str(exc)}


def _base_template(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>body{{font-family:Inter,Arial,sans-serif;background:#0b0d10;color:#f8fafc;padding:24px}}.card{{max-width:660px;margin:auto;background:#12161b;border:1px solid #27303a;border-radius:16px;padding:32px}}.brand{{color:#a78bfa;font-weight:800;letter-spacing:.14em;font-size:12px}}h1{{font-size:24px;margin:18px 0}}p,td{{color:#b6c0cc;line-height:1.6;font-size:14px}}table{{width:100%;border-collapse:collapse;margin:20px 0}}td{{border-bottom:1px solid #27303a;padding:10px 0}}td:first-child{{color:#7d8997;width:38%}}.footer{{border-top:1px solid #27303a;padding-top:18px;color:#697585;font-size:12px}}</style></head><body><div class='card'><div class='brand'>KLYPUP AI · PRICING INTELLIGENCE</div><h1>{title}</h1>{body}<div class='footer'>This is an automated governance notification from Klypup. Do not reply to this message.</div></div></body></html>"""


def send_login_email(user_email: str, user_name: str, ip_address: str = "unknown", user_agent: str = "unknown", session_id: str = "not available", event: str = "LOGIN") -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    body = f"<p>We recorded a secure workspace {html.escape(event.lower())} for <strong>{html.escape(user_name)}</strong>.</p><table><tr><td>Timestamp</td><td>{timestamp}</td></tr><tr><td>IP address</td><td>{html.escape(ip_address)}</td></tr><tr><td>User-Agent</td><td>{html.escape(user_agent)}</td></tr><tr><td>Session</td><td>{html.escape(session_id)}</td></tr></table>"
    return _send_or_archive_email(user_email, f"Klypup secure workspace {event.lower()}", _base_template("Secure workspace activity", body))


def send_registration_email(user_email: str, user_name: str) -> dict[str, Any]:
    return send_login_email(user_email, user_name, event="REGISTRATION")


def send_recommendation_action_email(user_email: str, action_type: str, product_details: dict, recommendation_details: dict, competitor_prices: list, action_id: str | None = None, user_role: str = "unknown") -> dict[str, Any]:
    from itsdangerous import URLSafeSerializer
    from flask import current_app

    labels = {"approve": "APPROVED", "reject": "REJECTED", "rollback": "ROLLED_BACK", "auto_execute": "AUTO_EXECUTED"}
    action_label = labels.get(action_type, action_type.upper())
    timestamp = datetime.now(timezone.utc).isoformat()
    product_name = product_details.get("name", "Unknown product")
    product_sku = product_details.get("sku", "N/A")
    product_category = product_details.get("category", "General")
    
    old_price = float(recommendation_details.get("previous_price", product_details.get("base_price", 0)))
    new_price = float(recommendation_details.get("executed_price", recommendation_details.get("recommended_price", 0)))

    competitor_reference = product_details.get("competitor_reference_price")
    if competitor_reference is None and competitor_prices:
        values = [float(row.get("competitor_price")) for row in competitor_prices if row.get("competitor_price")]
        competitor_reference = min(values) if values else None
    competitor_reference_text = f"₹{float(competitor_reference):,.2f}" if competitor_reference is not None else "Not available"

    llm_statement = recommendation_details.get("rationale") or recommendation_details.get("llm_statement") or "Consensus reached between Market & Inventory Analyst and Competitor Strategist."

    # Verified competitor comparison table with live clickable hyperlinks
    competitor_table_html = ""
    if competitor_prices:
        rows = []
        for item in competitor_prices:
            c_name = html.escape(str(item.get("competitor_name", "Marketplace")))
            c_price = float(item.get("competitor_price", 0))
            m_score = float(item.get("match_score", 1.0))
            p_url = item.get("product_url", "")
            if p_url and p_url.startswith("http"):
                link_html = f"<a href='{html.escape(p_url)}' target='_blank' rel='noopener noreferrer' style='color:#a78bfa;font-weight:500;text-decoration:none;'>Inspect Live Listing &rarr;</a>"
            else:
                link_html = "<span style='color:#7d8997;'>Direct listing</span>"
            rows.append(
                f"<tr><td style='color:#f8fafc;'>{c_name}</td><td style='color:#e2e8f0;font-weight:600;'>₹{c_price:,.2f}</td><td>{int(m_score * 100)}%</td><td>{link_html}</td></tr>"
            )
        competitor_table_html = f"""
        <h3 style='margin-top:24px;font-size:15px;color:#f8fafc;letter-spacing:0.02em;'>Verified Competitor Comparison Table</h3>
        <table style='width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;'>
          <thead>
            <tr style='color:#a78bfa;border-bottom:1px solid #27303a;text-align:left;'>
              <th style='padding:8px 0;'>Marketplace</th>
              <th style='padding:8px 0;'>Live Price</th>
              <th style='padding:8px 0;'>Match</th>
              <th style='padding:8px 0;'>Listing Hyperlink</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
        """

    # Cryptographically signed One-Click Rollback link
    rollback_section = ""
    if action_id and action_type in ("approve", "AUTO_EXECUTE", "auto_execute"):
        try:
            secret = current_app.config.get("SECRET_KEY", "klypup_super_secret_flask_key")
        except Exception:
            secret = os.environ.get("SECRET_KEY", "klypup_super_secret_flask_key")
        serializer = URLSafeSerializer(secret)
        rollback_token = serializer.dumps(str(action_id))
        api_root = os.environ.get("KLYPUP_API", "https://dynamic-pricing-intelligence-api.vercel.app/api").rstrip("/api")
        rollback_url = f"{api_root}/api/approvals/email-rollback/{rollback_token}"
        rollback_section = f"""
        <div style='margin:24px 0;padding:18px;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.3);border-radius:10px;text-align:center;'>
            <p style='color:#fca5a5;margin:0 0 12px 0;font-size:13px;line-height:1.5;'>Need to revert this change? Trigger an immediate cryptographic catalog restoration.</p>
            <a href='{rollback_url}' target='_blank' rel='noopener noreferrer' style='background:#ef4444;color:#ffffff;padding:11px 22px;border-radius:6px;text-decoration:none;font-weight:700;display:inline-block;font-size:13px;letter-spacing:0.02em;'>
                One-Click Rollback Price &rarr;
            </a>
            <div style='margin-top:8px;font-size:11px;color:#7d8997;'>Signed URLSafeSerializer Token: <code>{html.escape(rollback_token[:16])}...</code></div>
        </div>
        """

    body = f"""
    <p><strong>Action type:</strong> {action_label}</p>
    <table>
      <tr><td>Product</td><td><strong>{html.escape(str(product_name))}</strong></td></tr>
      <tr><td>SKU</td><td><code>{html.escape(str(product_sku))}</code></td></tr>
      <tr><td>Category</td><td>{html.escape(str(product_category))}</td></tr>
      <tr><td>Old Price</td><td style='color:#94a3b8;text-decoration:line-through;'>₹{old_price:,.2f}</td></tr>
      <tr><td>Executed New Price</td><td style='color:#34d399;font-weight:700;'>₹{new_price:,.2f}</td></tr>
      <tr><td>Competitor Reference</td><td>{competitor_reference_text}</td></tr>
      <tr><td>Timestamp</td><td>{timestamp}</td></tr>
      <tr><td>Authorized By</td><td>{html.escape(user_email)} ({html.escape(user_role)})</td></tr>
    </table>
    {competitor_table_html}
    <h3 style='margin-top:20px;font-size:15px;color:#f8fafc;'>LLM Decision Statement</h3>
    <p style='background:rgba(255,255,255,0.03);padding:14px;border-radius:8px;border:1px solid #27303a;color:#cbd5e1;line-height:1.6;'>
      {html.escape(str(llm_statement))}
    </p>
    {rollback_section}
    <p class='footer'>Audit action ID: {html.escape(str(action_id or recommendation_details.get('id', 'N/A')))}</p>
    """
    return _send_or_archive_email(user_email, f"Klypup pricing action {action_label}: {product_name}", _base_template(f"Pricing action {action_label}", body))
