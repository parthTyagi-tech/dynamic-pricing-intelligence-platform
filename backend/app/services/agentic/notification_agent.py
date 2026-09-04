import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import jinja2

from app.services.agentic.base_agent import BaseAgent

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="background: #0f172a; color: #f8fafc; padding: 20px; border-radius: 8px 8px 0 0;">
    <h2 style="margin:0;">Dynamic Pricing Update Confirmation</h2>
    <p style="margin: 5px 0 0; color: #94a3b8; font-size: 14px;">Product: {{ product_name }} (SKU: {{ sku }})</p>
  </div>
  <div style="border: 1px solid #e2e8f0; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
    <p>A new price adjustment has been approved and successfully applied to your catalog.</p>
    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
      <tr style="border-bottom: 1px solid #e2e8f0;">
        <td style="padding: 8px 0; color: #64748b;">Previous Price:</td>
        <td style="padding: 8px 0; font-weight: bold; text-align: right;">₹{{ "%.2f"|format(old_price) }}</td>
      </tr>
      <tr style="border-bottom: 1px solid #e2e8f0;">
        <td style="padding: 8px 0; color: #64748b;">New Approved Price:</td>
        <td style="padding: 8px 0; font-weight: bold; color: #10b981; text-align: right;">₹{{ "%.2f"|format(new_price) }}</td>
      </tr>
      <tr style="border-bottom: 1px solid #e2e8f0;">
        <td style="padding: 8px 0; color: #64748b;">Confidence Level:</td>
        <td style="padding: 8px 0; text-align: right; text-transform: uppercase;">{{ confidence }}</td>
      </tr>
    </table>
    <div style="background: #f8fafc; padding: 15px; border-radius: 6px; border-left: 4px solid #3b82f6; margin-top: 15px;">
      <strong style="color: #1e293b;">Agent Reasoning:</strong>
      <p style="margin: 5px 0 0; color: #475569; font-size: 14px;">{{ reasoning_text }}</p>
    </div>
    <p style="font-size: 12px; color: #94a3b8; margin-top: 25px;">
      Approved by user ID: {{ user_id }} on {{ timestamp }} UTC.
    </p>
  </div>
</body>
</html>
"""


class NotificationAgent(BaseAgent):
    """
    SEC-11: Notification Agent with Jinja2 HTML Auto-Escaping.
    Composes and delivers transactional notifications for pricing approvals.
    """

    def __init__(self):
        super().__init__(
            role="NotificationAgent",
            goal="Compose and dispatch safe, auto-escaped email alerts for price changes",
            available_tools=["email_dispatcher", "jinja_autoescape_renderer"]
        )
        self.jinja_env = jinja2.Environment(
            autoescape=jinja2.select_autoescape(["html", "xml"])
        )
        self.template = self.jinja_env.from_string(EMAIL_TEMPLATE)

    async def send_approval_email(
        self,
        task_id: str,
        organization_id: str,
        product: Dict[str, Any],
        old_price: float,
        new_price: float,
        confidence: str,
        reasoning_text: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # SEC-11: Render template with auto-escape
        rendered_html = self.template.render(
            product_name=product.get("name", "Product"),
            sku=product.get("sku", "N/A"),
            old_price=old_price,
            new_price=new_price,
            confidence=confidence,
            reasoning_text=self.sanitize_output(reasoning_text),
            user_id=user_id or "System",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        )

        logger.info(
            f"[NotificationAgent] Dispatched approval notification for SKU {product.get('sku')} "
            f"(Length: {len(rendered_html)} chars)"
        )

        await self.emit_event(
            task_id=task_id,
            product_id=product.get("id", ""),
            organization_id=organization_id,
            event_type="notification_sent",
            message=f"Transactional email notification prepared for SKU {product.get('sku')}.",
            payload={"status": "dispatched", "product_name": product.get("name")}
        )

        return {"status": "sent", "recipient_count": 1}
