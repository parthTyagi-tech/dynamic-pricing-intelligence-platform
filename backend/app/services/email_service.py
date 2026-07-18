import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Directory to dump mock email HTML files for local verification
EMAILS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "emails")
os.makedirs(EMAILS_DIR, exist_ok=True)


def _send_or_save_email(to_email: str, subject: str, html_content: str):
    """Sends email via SMTP if configured, otherwise dumps to HTML file for inspection."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = os.environ.get("SMTP_PORT")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    sender_email = os.environ.get("SMTP_SENDER", "alerts@klypup.com")

    # Always dump locally for development/observability
    safe_subject = "".join(c for c in subject if c.isalnum() or c in (" ", "-", "_")).rstrip()
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{safe_subject}.html"
    filepath = os.path.join(EMAILS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[Email Service] Mock email generated successfully: {filepath}")

    if smtp_host and smtp_port and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender_email
            msg["To"] = to_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(smtp_host, int(smtp_port), timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(sender_email, to_email, msg.as_string())
            print(f"[Email Service] Live SMTP email sent successfully to: {to_email}")
        except Exception as e:
            print(f"[Email Service] Live SMTP failed: {e}. (Mock file preserved).")


def send_registration_email(user_email: str, user_name: str):
    """Sends a welcoming onboard email to a newly registered user."""
    subject = "Welcome to Klypup Dynamic Pricing Platform!"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0b0f19; color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 40px; box-shadow: 0 4px 30px rgba(0,0,0,0.4); }}
            .logo {{ font-size: 24px; font-weight: bold; color: #2dd4bf; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1.5px; }}
            h1 {{ font-size: 20px; color: #ffffff; margin-bottom: 16px; }}
            p {{ font-size: 14px; line-height: 1.6; color: #94a3b8; }}
            .footer {{ margin-top: 40px; border-top: 1px solid #1e293b; padding-top: 20px; font-size: 12px; color: #64748b; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">Klypup AI</div>
            <h1>Welcome aboard, {user_name}!</h1>
            <p>Your pricing optimization account has been successfully initialized.</p>
            <p>You can now upload your catalog, track real-time competitor prices across 6 storefront platforms (Amazon, Flipkart, Walmart, Ebay, BestBuy, and Target), and approve LLM-optimized pricing recommendations.</p>
            <div class="footer">
                This is an automated system notification from Klypup. Please do not reply directly.
            </div>
        </div>
    </body>
    </html>
    """
    _send_or_save_email(user_email, subject, html_content)


def send_recommendation_action_email(
    user_email: str,
    action_type: str,
    product_details: dict,
    recommendation_details: dict,
    competitor_prices: list,
    action_id: str = None
):
    """Sends a structured transaction report for any pricing action (approve/reject/rollback)."""
    action_verb = "Approved" if action_type == "approve" else ("Rejected" if action_type == "reject" else ("Rolled Back" if action_type == "rollback" else "Auto-Executed"))
    subject = f"[Klypup Alert] Pricing Recommendation {action_verb} for {product_details.get('name')}"

    rollback_html = ""
    if action_type in ("approve", "auto_execute") and action_id:
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer(os.environ.get("SECRET_KEY", "dev-secret-key"))
        token = s.dumps(action_id)
        # Using a generic localhost or environment variable for the domain
        domain = os.environ.get("BASE_URL", "http://localhost:5000")
        rollback_link = f"{domain}/api/approvals/email-rollback/{token}"
        rollback_html = f"""
        <div style="text-align:center; margin-top: 20px; margin-bottom: 20px;">
            <p style="color: #94a3b8; font-size: 12px; margin-bottom: 10px;">If this AI recommendation is incorrect, you can immediately revert the live store price.</p>
            <a href="{rollback_link}" style="display:inline-block; background-color: #ef4444; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 14px; box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3);">
                UNDO & ROLLBACK PRICE
            </a>
        </div>
        """

    # Competitor Pricing rows builder
    competitor_rows = ""
    if competitor_prices:
        for c in competitor_prices:
            in_stock_badge = '<span style="color:#10b981;font-weight:bold;">In Stock</span>' if c.get("in_stock", True) else '<span style="color:#ef4444;">Out of stock</span>'
            competitor_rows += f"""
            <tr>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#f1f5f9;">{c.get('competitor_name')}</td>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#f1f5f9;">{in_stock_badge}</td>
                <td style="padding:10px;border-bottom:1px solid #1e293b;color:#2dd4bf;font-weight:bold;font-family:monospace;">₹{c.get('competitor_price'):.2f}</td>
            </tr>
            """
    else:
        competitor_rows = "<tr><td colspan='3' style='padding:10px;text-align:center;color:#64748b;font-style:italic;'>No competitor price checks recorded.</td></tr>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #0b0f19; color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 650px; margin: 0 auto; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 16px; padding: 40px; box-shadow: 0 4px 30px rgba(0,0,0,0.4); }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 20px; margin-bottom: 24px; }}
            .logo {{ font-size: 20px; font-weight: bold; color: #2dd4bf; text-transform: uppercase; letter-spacing: 1.5px; }}
            .badge {{ padding: 6px 12px; border-radius: 9999px; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
            .badge-approve {{ background-color: rgba(16,185,129,0.1); color: #10b981; border: 1px solid rgba(16,185,129,0.2); }}
            .badge-reject {{ background-color: rgba(239,68,68,0.1); color: #ef4444; border: 1px solid rgba(239,68,68,0.2); }}
            .badge-rollback {{ background-color: rgba(99,102,241,0.1); color: #818cf8; border: 1px solid rgba(99,102,241,0.2); }}
            h2 {{ font-size: 18px; color: #ffffff; margin-top: 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 25px; }}
            th {{ text-align: left; padding: 10px; background-color: #1e293b; color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}
            .field-name {{ font-weight: bold; color: #94a3b8; width: 30%; padding: 8px 0; font-size: 13px; }}
            .field-value {{ color: #ffffff; padding: 8px 0; font-size: 13px; }}
            .block {{ background-color: #070a13; border: 1px solid #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 25px; }}
            .rationale-text {{ font-size: 13px; color: #cbd5e1; line-height: 1.6; margin: 0; }}
            .footer {{ border-top: 1px solid #1e293b; padding-top: 20px; font-size: 12px; color: #64748b; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">Klypup Action Alert</div>
                <span class="badge badge-{action_type}">{action_verb}</span>
            </div>
            
            <h2>Pricing Action Summary</h2>
            <table>
                <tr>
                    <td class="field-name">Product Name</td>
                    <td class="field-value">{product_details.get('name')}</td>
                </tr>
                <tr>
                    <td class="field-name">Product SKU</td>
                    <td class="field-value" style="font-family:monospace;">{product_details.get('sku')}</td>
                </tr>
                <tr>
                    <td class="field-name">Previous price</td>
                    <td class="field-value" style="font-weight:bold;">₹{recommendation_details.get('previous_price', 0.0):.2f}</td>
                </tr>
                <tr>
                    <td class="field-name">Action price</td>
                    <td class="field-value" style="font-weight:bold;color:#2dd4bf;">
                        ₹{recommendation_details.get('executed_price', 0.0):.2f}
                    </td>
                </tr>
                <tr>
                    <td class="field-name">Action time</td>
                    <td class="field-value">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
                </tr>
            </table>

            <h2>LLM Rationale & Strategy Statement</h2>
            <div class="block">
                <p class="rationale-text">
                    {recommendation_details.get('rationale', 'No rationale provided.')}
                </p>
                <p style="font-size:11px;color:#64748b;margin-top:10px;margin-bottom:0;">
                    Optimization Confidence Score: <b>{int(recommendation_details.get('confidence_score', 0.0) * 100)}%</b>
                </p>
            </div>

            <h2>Competitor Storefront Price Comparison</h2>
            <table>
                <thead>
                    <tr>
                        <th style="padding:10px;">Storefront</th>
                        <th style="padding:10px;">Availability</th>
                        <th style="padding:10px;">Price</th>
                    </tr>
                </thead>
                <tbody>
                    {competitor_rows}
                </tbody>
            </table>

            {rollback_html}

            <div class="footer">
                Governance tracking ID: {recommendation_details.get('id', 'N/A')}<br>
                This is an automated security audit email from Klypup. Please do not reply.
            </div>
        </div>
    </body>
    </html>
    """
    _send_or_save_email(user_email, subject, html_content)
