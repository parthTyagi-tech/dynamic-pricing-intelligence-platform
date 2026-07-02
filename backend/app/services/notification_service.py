"""
Enterprise Notification Service
Simulates sending high-priority alerts to external systems like Slack or Microsoft Teams.
"""
import logging
from datetime import datetime, timezone
from flask import current_app

logger = logging.getLogger(__name__)

def send_slack_alert(message: str, recommendation: dict, product: dict):
    """
    Simulates sending a Slack webhook alert for high-impact pricing changes.
    In production, this would make an HTTP POST request to a Slack webhook URL.
    """
    
    # Check if this is a high impact change (e.g., > 5% drop or high profit lift)
    price_change = recommendation.get("price_change_pct", 0)
    profit_lift = recommendation.get("projected_monthly_profit_lift", 0)
    
    if abs(price_change) < 5.0 and profit_lift < 50.0:
        return # Skip low impact changes
        
    slack_payload = {
        "text": message,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 High Priority Pricing Alert: {product.get('name')}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Current Price:*\n${product.get('current_price')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Recommended Price:*\n${recommendation.get('recommended_price')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Change %:*\n{price_change}%"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Projected Profit Lift:*\n+${profit_lift}/mo"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Rationale:*\n{recommendation.get('rationale')}"
                }
            }
        ]
    }
    
    # Simulate the network call
    logger.info("=== 🔔 SLACK ALERT DISPATCHED ===")
    logger.info(f"Payload: {slack_payload}")
    logger.info("=================================")
    
    # Store in memory for the UI to fetch if needed
    if not hasattr(current_app, "alert_logs"):
        current_app.alert_logs = []
        
    current_app.alert_logs.insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "product_name": product.get("name"),
        "message": message,
        "price_change": price_change,
        "profit_lift": profit_lift
    })
    
    # Keep only recent 50
    current_app.alert_logs = current_app.alert_logs[:50]
