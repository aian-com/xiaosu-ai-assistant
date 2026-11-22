"""Initial schema. This migration is explicit and independent of runtime ORM metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("documents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False, unique=True), sa.Column("active_version", sa.String(36)), sa.Column("latest_version", sa.String(36)), sa.Column("deleted", sa.Boolean(), nullable=False))
    op.create_table("versions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False), sa.Column("digest", sa.String(64), nullable=False), sa.Column("path", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("error", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_versions_document_id", "versions", ["document_id"])
    op.create_table("chunks", sa.Column("id", sa.String(36), primary_key=True), sa.Column("version_id", sa.String(36), sa.ForeignKey("versions.id"), nullable=False), sa.Column("ordinal", sa.Integer(), nullable=False), sa.Column("location", sa.String(255), nullable=False), sa.Column("text", sa.Text(), nullable=False), sa.Column("embedding", sa.JSON(), nullable=False), sa.Column("embedding_model", sa.String(255), nullable=False))
    op.create_index("ix_chunks_version_id", "chunks", ["version_id"])
    op.create_table("jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("version_id", sa.String(36), sa.ForeignKey("versions.id"), nullable=False, unique=True), sa.Column("status", sa.String(20), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("conversations", sa.Column("id", sa.String(64), primary_key=True), sa.Column("platform", sa.String(32), nullable=False), sa.Column("tenant_id", sa.String(255), nullable=False), sa.Column("user_id", sa.String(255), nullable=False), sa.Column("channel_id", sa.String(255), nullable=False))
    op.create_table("messages", sa.Column("id", sa.String(36), primary_key=True), sa.Column("platform", sa.String(32), nullable=False), sa.Column("external_id", sa.String(255), nullable=False), sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False), sa.Column("question", sa.Text(), nullable=False), sa.Column("answer", sa.Text(), nullable=False), sa.Column("citations", sa.JSON(), nullable=False), sa.Column("tool_calls", sa.JSON(), nullable=False), sa.Column("usage", sa.JSON()), sa.Column("error", sa.Text()), sa.Column("status", sa.String(20), nullable=False), sa.Column("delivery", sa.String(20), nullable=False), sa.Column("reply_url", sa.Text()), sa.Column("latency_ms", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("platform", "external_id"))
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table("settings", sa.Column("key", sa.String(100), primary_key=True), sa.Column("value", sa.JSON(), nullable=False))


def downgrade():
    for table in ["settings", "messages", "conversations", "jobs", "chunks", "versions", "documents"]:
        op.drop_table(table)
