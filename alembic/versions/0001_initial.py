"""Initial schema + seed admin user

Revision ID: 0001
Revises:
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_USERS_ID = "users.id"
_DATASETS_ID = "datasets.id"
_SET_NULL = "SET NULL"
_CASCADE = "CASCADE"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_USERS_ID, ondelete=_SET_NULL)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "encryption_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_DATASETS_ID, ondelete=_CASCADE), unique=True),
        sa.Column("encrypted_key", sa.LargeBinary, nullable=False),
        sa.Column("key_ref", sa.String(24), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_USERS_ID, ondelete=_SET_NULL)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rbac_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_USERS_ID, ondelete=_CASCADE)),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_DATASETS_ID, ondelete=_CASCADE)),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_USERS_ID, ondelete=_SET_NULL)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "dataset_id", "entity_type", name="uq_rbac_grant"),
    )
    op.create_index("ix_rbac_grants_user_id", "rbac_grants", ["user_id"])
    op.create_index("ix_rbac_grants_dataset_id", "rbac_grants", ["dataset_id"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_USERS_ID, ondelete=_CASCADE)),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_DATASETS_ID, ondelete=_SET_NULL)),
        sa.Column("title", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chat_sessions.id", ondelete=_CASCADE)),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_USERS_ID, ondelete=_SET_NULL)),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("token", sa.String(100), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey(_DATASETS_ID, ondelete=_SET_NULL)),
        sa.Column("action", sa.String(50), nullable=False, server_default="decrypt"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), index=True),
    )

    # Seed admin user — password: admin (change immediately in production!)
    op.execute("""
        INSERT INTO users (id, email, hashed_password, role, is_active)
        VALUES (
            gen_random_uuid(),
            'admin@tux.ai',
            '$2b$12$ptrxh8roA8IacsyOM1kcD.t0irUKF2s9qYFx6YlEE1TSU8pHbAp6.',
            'admin',
            true
        )
    """)


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("messages")
    op.drop_table("chat_sessions")
    op.drop_table("rbac_grants")
    op.drop_table("encryption_keys")
    op.drop_table("datasets")
    op.drop_table("users")
