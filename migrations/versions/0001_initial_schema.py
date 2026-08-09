"""Initial customer, screening case, and audit event schema."""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Optional[str] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("record_id", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("legal_name", sa.String(length=500), nullable=False),
        sa.Column("normalized_name", sa.String(length=500), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("registered_country", sa.String(length=2), nullable=True),
        sa.Column("registration_number", sa.String(length=100), nullable=True),
        sa.Column("normalized_registration_number", sa.String(length=100), nullable=True),
        sa.Column("lei", sa.String(length=20), nullable=True),
        sa.Column("incorporation_date", sa.Date(), nullable=True),
        sa.Column("last_kyc_review", sa.Date(), nullable=True),
        sa.Column("aum_usd_millions", sa.Float(), nullable=True),
        sa.Column("is_pep", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id"),
    )
    for column in (
        "normalized_name",
        "registered_country",
        "registration_number",
        "normalized_registration_number",
        "lei",
    ):
        op.create_index(f"ix_customers_{column}", "customers", [column])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])

    op.create_table(
        "screening_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("dataset_version", sa.String(length=100), nullable=False),
        sa.Column("matched_entity_id", sa.String(length=100), nullable=False),
        sa.Column("matched_name", sa.String(length=500), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_screening_cases_customer_id", "screening_cases", ["customer_id"])
    op.create_index("ix_screening_cases_status", "screening_cases", ["status"])


def downgrade() -> None:
    op.drop_index("ix_screening_cases_status", table_name="screening_cases")
    op.drop_index("ix_screening_cases_customer_id", table_name="screening_cases")
    op.drop_table("screening_cases")
    op.drop_index("ix_audit_events_entity_id", table_name="audit_events")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_table("audit_events")
    for column in (
        "lei",
        "normalized_registration_number",
        "registration_number",
        "registered_country",
        "normalized_name",
    ):
        op.drop_index(f"ix_customers_{column}", table_name="customers")
    op.drop_table("customers")
