"""add insulin open validity days

Revision ID: f3a7c1d8e4b2
Revises: a8f1c6d92e3b
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c1d8e4b2'
down_revision: Union[str, Sequence[str], None] = 'a8f1c6d92e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'insulin',
        sa.Column(
            'open_validity_days',
            sa.Integer(),
            nullable=False,
            server_default='28',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('insulin', 'open_validity_days')
