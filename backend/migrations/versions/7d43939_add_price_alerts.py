"""add persistent competitor price alerts

Revision ID: 7d43939
Revises: 019544ea1e46
"""
from alembic import op
import sqlalchemy as sa

revision = "7d43939"
down_revision = "019544ea1e46"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("competitor_name", sa.String(length=255), nullable=False),
        sa.Column("previous_price", sa.Float(), nullable=False),
        sa.Column("current_price", sa.Float(), nullable=False),
        sa.Column("drop_percent", sa.Float(), nullable=False),
        sa.Column("drop_amount", sa.Float(), nullable=False),
        sa.Column("threshold_percent", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_price_alerts_organization_id", "price_alerts", ["organization_id"])
    op.create_index("ix_price_alerts_product_id", "price_alerts", ["product_id"])
    op.create_index("ix_price_alerts_competitor_name", "price_alerts", ["competitor_name"])
    op.create_index("ix_price_alerts_status", "price_alerts", ["status"])
    op.create_index("ix_price_alerts_detected_at", "price_alerts", ["detected_at"])


def downgrade():
    op.drop_index("ix_price_alerts_detected_at", table_name="price_alerts")
    op.drop_index("ix_price_alerts_status", table_name="price_alerts")
    op.drop_index("ix_price_alerts_competitor_name", table_name="price_alerts")
    op.drop_index("ix_price_alerts_product_id", table_name="price_alerts")
    op.drop_index("ix_price_alerts_organization_id", table_name="price_alerts")
    op.drop_table("price_alerts")
