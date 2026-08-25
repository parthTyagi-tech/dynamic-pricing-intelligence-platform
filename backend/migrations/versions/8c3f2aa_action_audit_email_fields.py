"""add action audit and email delivery fields

Revision ID: 8c3f2aa
Revises: 7d43939
"""
from alembic import op
import sqlalchemy as sa

revision = "8c3f2aa"
down_revision = "7d43939"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("approval_actions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sku", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("llm_statement", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("user_email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("email_sent_status", sa.String(length=32), nullable=False, server_default="pending"))
        batch_op.add_column(sa.Column("email_provider_message_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("email_error", sa.Text(), nullable=True))
        batch_op.create_index("ix_approval_actions_sku", ["sku"], unique=False)


def downgrade():
    with op.batch_alter_table("approval_actions", schema=None) as batch_op:
        batch_op.drop_index("ix_approval_actions_sku")
        batch_op.drop_column("email_error")
        batch_op.drop_column("email_provider_message_id")
        batch_op.drop_column("email_sent_status")
        batch_op.drop_column("user_email")
        batch_op.drop_column("llm_statement")
        batch_op.drop_column("sku")
