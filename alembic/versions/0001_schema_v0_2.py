"""Alembic revision for schema v0.2 SQL contract."""

from pathlib import Path

from alembic import op

revision = "0001_schema_v0_2"
down_revision = None
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parents[2] / "sql"


def upgrade() -> None:
    op.execute((SQL_DIR / "0001_schema_v0_2.sql").read_text(encoding="utf-8"))
    op.execute((SQL_DIR / "0002_roles.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS intelligence CASCADE")
