"""Record provenance for bounded stream verification results."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_stream_verification_provenance"
down_revision: str | None = "0014_stream_gap_recovery_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stream_verifications", sa.Column("provider_id", sa.String(128)))
    op.add_column("stream_verifications", sa.Column("program_scope", sa.String(512)))
    op.add_column("stream_verifications", sa.Column("commitment", sa.String(32)))
    op.add_column("stream_verifications", sa.Column("verification_method", sa.String(128)))
    op.add_column("stream_verifications", sa.Column("recovery_attempt", sa.Integer()))


def downgrade() -> None:
    op.drop_column("stream_verifications", "recovery_attempt")
    op.drop_column("stream_verifications", "verification_method")
    op.drop_column("stream_verifications", "commitment")
    op.drop_column("stream_verifications", "program_scope")
    op.drop_column("stream_verifications", "provider_id")
