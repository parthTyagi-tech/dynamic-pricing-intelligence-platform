"""add agentic v2 columns and tables

Revision ID: e8c5a21f7d90
Revises: d64a4f3b1a21
"""
from alembic import op
import sqlalchemy as sa

revision = "e8c5a21f7d90"
down_revision = "d64a4f3b1a21"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Update pricing_recommendations
    with op.batch_alter_table("pricing_recommendations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("task_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("platform_prices_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("margin_floor_applied", sa.Boolean(), nullable=False, server_default="false"))
        batch_op.add_column(sa.Column("margin_floor_value", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("sanity_bound_flagged", sa.Boolean(), nullable=False, server_default="false"))
        batch_op.add_column(sa.Column("decided_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("decided_by", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_pricing_recommendations_task_id", ["task_id"], unique=False)

    # 2. Update audit_logs
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("before_value", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("after_value", sa.JSON(), nullable=True))

    # 3. Create price_histories table if not exists
    op.create_table(
        "price_histories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("recommendation_id", sa.String(length=36), sa.ForeignKey("pricing_recommendations.id"), nullable=True, index=True),
        sa.Column("old_price", sa.Float(), nullable=False),
        sa.Column("new_price", sa.Float(), nullable=False),
        sa.Column("competitor_prices", sa.JSON(), nullable=True),
        sa.Column("approved_by", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("organization_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # 4. Create scraper_reliabilities table if not exists
    op.create_table(
        "scraper_reliabilities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("platform", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("circuit_state", sa.String(length=20), nullable=False, server_default="closed"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_failure", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("scraper_reliabilities")
    op.drop_table("price_histories")
    with op.batch_alter_table("audit_logs", schema=None) as batch_op:
        batch_op.drop_column("after_value")
        batch_op.drop_column("before_value")
    with op.batch_alter_table("pricing_recommendations", schema=None) as batch_op:
        batch_op.drop_index("ix_pricing_recommendations_task_id")
        batch_op.drop_column("decided_by")
        batch_op.drop_column("decided_at")
        batch_op.drop_column("sanity_bound_flagged")
        batch_op.drop_column("margin_floor_value")
        batch_op.drop_column("margin_floor_applied")
        batch_op.drop_column("platform_prices_snapshot")
        batch_op.drop_column("task_id")
