"""Add durable recommendation jobs and marketplace offers.

Revision ID: d64a4f3b1a21
Revises: 8c3f2aa
"""

from alembic import op
import sqlalchemy as sa


revision = "d64a4f3b1a21"
down_revision = "8c3f2aa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recommendation_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recommendation_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("current_agent", sa.String(length=64), nullable=True),
        sa.Column("requested_platforms", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["pricing_recommendations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id"),
    )
    op.create_index("ix_recommendation_jobs_recommendation_id", "recommendation_jobs", ["recommendation_id"], unique=True)
    op.create_index("ix_recommendation_jobs_product_id", "recommendation_jobs", ["product_id"], unique=False)
    op.create_index("ix_recommendation_jobs_organization_id", "recommendation_jobs", ["organization_id"], unique=False)
    op.create_index("ix_recommendation_jobs_status", "recommendation_jobs", ["status"], unique=False)
    op.create_index("ix_recommendation_jobs_available_at", "recommendation_jobs", ["available_at"], unique=False)

    op.create_table(
        "recommendation_agent_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["recommendation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendation_agent_events_job_id", "recommendation_agent_events", ["job_id"], unique=False)
    op.create_index("ix_recommendation_agent_events_agent_name", "recommendation_agent_events", ["agent_name"], unique=False)

    op.create_table(
        "marketplace_offers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(length=128), nullable=True),
        sa.Column("variant", sa.String(length=255), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("mrp", sa.Float(), nullable=True),
        sa.Column("availability", sa.String(length=64), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=True),
        sa.Column("specifications", sa.JSON(), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("offers", sa.JSON(), nullable=True),
        sa.Column("product_url", sa.Text(), nullable=True),
        sa.Column("match_confidence", sa.String(length=16), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["recommendation_jobs.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_marketplace_offers_job_id", "marketplace_offers", ["job_id"], unique=False)
    op.create_index("ix_marketplace_offers_product_id", "marketplace_offers", ["product_id"], unique=False)
    op.create_index("ix_marketplace_offers_organization_id", "marketplace_offers", ["organization_id"], unique=False)
    op.create_index("ix_marketplace_offers_platform", "marketplace_offers", ["platform"], unique=False)


def downgrade():
    op.drop_index("ix_marketplace_offers_platform", table_name="marketplace_offers")
    op.drop_index("ix_marketplace_offers_organization_id", table_name="marketplace_offers")
    op.drop_index("ix_marketplace_offers_product_id", table_name="marketplace_offers")
    op.drop_index("ix_marketplace_offers_job_id", table_name="marketplace_offers")
    op.drop_table("marketplace_offers")
    op.drop_index("ix_recommendation_agent_events_agent_name", table_name="recommendation_agent_events")
    op.drop_index("ix_recommendation_agent_events_job_id", table_name="recommendation_agent_events")
    op.drop_table("recommendation_agent_events")
    op.drop_index("ix_recommendation_jobs_available_at", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_status", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_organization_id", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_product_id", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_recommendation_id", table_name="recommendation_jobs")
    op.drop_table("recommendation_jobs")
