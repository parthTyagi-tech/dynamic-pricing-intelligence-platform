"""
WhatsApp Notification Service
Sends WhatsApp messages via Twilio for registration welcome and pricing action alerts.
Falls back to console logging when Twilio credentials are not configured.
"""
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Directory to dump mock WhatsApp messages for local verification
WHATSAPP_LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "whatsapp_logs"
)
os.makedirs(WHATSAPP_LOGS_DIR, exist_ok=True)


def _get_twilio_client():
    """Returns a Twilio client if credentials are configured, else None."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")

    if account_sid and auth_token:
        try:
            from twilio.rest import Client
            return Client(account_sid, auth_token)
        except ImportError:
            logger.warning("[WhatsApp Service] twilio package not installed. Falling back to mock.")
            return None
    return None


def _send_or_log_whatsapp(to_phone: str, message_body: str):
    """Sends WhatsApp message via Twilio if configured, otherwise logs to file for inspection."""
    from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # Normalize phone number to WhatsApp format
    if not to_phone.startswith("whatsapp:"):
        to_phone = f"whatsapp:{to_phone}"

    # Always dump locally for development/observability
    safe_phone = to_phone.replace(":", "_").replace("+", "")
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{safe_phone}.txt"
    filepath = os.path.join(WHATSAPP_LOGS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"To: {to_phone}\n")
        f.write(f"From: {from_number}\n")
        f.write(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"{'=' * 50}\n")
        f.write(message_body)
    logger.info(f"[WhatsApp Service] Mock message saved: {filepath}")
    print(f"[WhatsApp Service] Mock WhatsApp message generated: {filepath}")

    client = _get_twilio_client()
    if client:
        try:
            msg = client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_phone,
            )
            logger.info(f"[WhatsApp Service] Message sent successfully. SID: {msg.sid}")
            print(f"[WhatsApp Service] Live WhatsApp sent to {to_phone}, SID: {msg.sid}")
        except Exception as e:
            logger.error(f"[WhatsApp Service] Failed to send via Twilio: {e}")
            print(f"[WhatsApp Service] Twilio send failed: {e}. (Mock file preserved).")


def send_whatsapp_welcome(phone_number: str, user_name: str):
    """Sends a welcome WhatsApp message to a newly registered user."""
    message_body = (
        f"🚀 *Welcome to Klypup, {user_name}!*\n\n"
        f"Your AI-powered pricing optimization account has been successfully created.\n\n"
        f"You can now:\n"
        f"📦 Upload your product catalog\n"
        f"📊 Track real-time competitor prices across 6 storefronts "
        f"(Amazon, Flipkart, Walmart, eBay, BestBuy, Target)\n"
        f"✅ Approve LLM-optimized pricing recommendations\n\n"
        f"_This is an automated message from Klypup AI. Please do not reply._"
    )
    _send_or_log_whatsapp(phone_number, message_body)


def send_whatsapp_recommendation_action(
    phone_number: str,
    action_type: str,
    product_details: dict,
    recommendation_details: dict,
    competitor_prices: list,
):
    """Sends a detailed pricing action WhatsApp alert (approve/reject/rollback)."""
    action_emoji = {"approve": "✅", "reject": "❌", "rollback": "🔄"}.get(action_type, "📋")
    action_verb = (
        "Approved" if action_type == "approve"
        else ("Rejected" if action_type == "reject" else "Rolled Back")
    )

    # Build competitor price lines
    competitor_lines = ""
    if competitor_prices:
        for c in competitor_prices:
            stock_status = "✅ In Stock" if c.get("in_stock", True) else "❌ Out of Stock"
            competitor_lines += (
                f"  • {c.get('competitor_name')}: ₹{c.get('competitor_price', 0):.2f} ({stock_status})\n"
            )
    else:
        competitor_lines = "  _No competitor data available._\n"

    confidence_pct = int(recommendation_details.get("confidence_score", 0) * 100)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    message_body = (
        f"{action_emoji} *Klypup Pricing Alert — {action_verb}*\n"
        f"{'━' * 30}\n\n"
        f"📦 *Product:* {product_details.get('name')}\n"
        f"🏷️ *SKU:* {product_details.get('sku')}\n\n"
        f"💰 *Previous Price:* ₹{recommendation_details.get('previous_price', 0):.2f}\n"
        f"💎 *{action_verb} Price:* ₹{recommendation_details.get('executed_price', 0):.2f}\n\n"
        f"🧠 *LLM Rationale:*\n"
        f"_{recommendation_details.get('rationale', 'No rationale provided.')}_\n\n"
        f"📈 *Confidence Score:* {confidence_pct}%\n\n"
        f"🏪 *Competitor Prices:*\n"
        f"{competitor_lines}\n"
        f"🕐 *Timestamp:* {timestamp}\n"
        f"🔖 *Tracking ID:* {recommendation_details.get('id', 'N/A')}\n"
        f"{'━' * 30}\n"
        f"_Automated alert from Klypup AI. Do not reply._"
    )
    _send_or_log_whatsapp(phone_number, message_body)
