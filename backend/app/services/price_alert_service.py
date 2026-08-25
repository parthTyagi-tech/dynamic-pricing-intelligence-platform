import os
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.price_alert import PriceAlert

DEFAULT_DROP_THRESHOLD_PCT = float(os.environ.get("COMPETITOR_DROP_ALERT_THRESHOLD_PCT", "5"))
DEFAULT_MIN_DROP_INR = float(os.environ.get("COMPETITOR_DROP_ALERT_MIN_INR", "100"))
DEFAULT_ALERT_COOLDOWN_MINUTES = int(os.environ.get("COMPETITOR_DROP_ALERT_COOLDOWN_MINUTES", "30"))


def detect_and_create_alerts(product, previous_prices: dict[str, float], current_prices: dict[str, float], threshold_pct: float | None = None, min_drop_inr: float | None = None):
    """Compare a newly ingested market snapshot against the previous snapshot.

    A drop is actionable only when both the percentage and absolute INR thresholds
    are exceeded. The same product/platform is suppressed during the cooldown
    window so repeated scraper cycles do not create alert storms.
    """
    threshold = float(threshold_pct if threshold_pct is not None else DEFAULT_DROP_THRESHOLD_PCT)
    minimum = float(min_drop_inr if min_drop_inr is not None else DEFAULT_MIN_DROP_INR)
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(minutes=DEFAULT_ALERT_COOLDOWN_MINUTES)
    created: list[PriceAlert] = []

    for competitor_name, raw_current in current_prices.items():
        current_price = float(raw_current or 0)
        previous_price = float(previous_prices.get(competitor_name) or 0)
        if previous_price <= 0 or current_price <= 0 or current_price >= previous_price:
            continue
        drop_amount = round(previous_price - current_price, 2)
        drop_percent = round((drop_amount / previous_price) * 100, 2)
        if drop_percent < threshold or drop_amount < minimum:
            continue
        duplicate = PriceAlert.query.filter(
            PriceAlert.organization_id == product.organization_id,
            PriceAlert.product_id == product.id,
            PriceAlert.competitor_name == competitor_name,
            PriceAlert.status == "open",
            PriceAlert.detected_at >= cooldown_cutoff,
        ).first()
        if duplicate:
            continue
        alert = PriceAlert(
            organization_id=product.organization_id,
            product_id=product.id,
            competitor_name=competitor_name,
            previous_price=previous_price,
            current_price=current_price,
            drop_percent=drop_percent,
            drop_amount=drop_amount,
            threshold_percent=threshold,
            status="open",
            detected_at=now,
        )
        db.session.add(alert)
        created.append(alert)
    return created


def acknowledge_alert(alert: PriceAlert):
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    return alert
