"""add insulin container tracking

Revision ID: a8f1c6d92e3b
Revises: 235076f62fb6
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f1c6d92e3b'
down_revision: Union[str, Sequence[str], None] = '235076f62fb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    container_status = sa.Enum(
        'SEALED', 'OPEN', 'EMPTY', 'DISCARDED',
        name='container_status',
    )

    op.create_table(
        'insulin_container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('insulin_id', sa.Integer(), nullable=False),
        sa.Column('initial_units', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', container_status, nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['insulin_id'], ['insulin.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column(
        'stock_movement',
        sa.Column('container_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'stock_movement',
        sa.Column('group_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'stock_movement_container_id_fkey',
        'stock_movement',
        'insulin_container',
        ['container_id'],
        ['id'],
    )
    op.create_foreign_key(
        'stock_movement_group_id_fkey',
        'stock_movement',
        'stock_movement',
        ['group_id'],
        ['id'],
    )

    _backfill_legacy_containers(op.get_bind())

    op.alter_column('stock_movement', 'container_id', nullable=False)


def _backfill_legacy_containers(bind) -> None:
    insulin_ids = bind.execute(
        sa.text(
            "SELECT DISTINCT insulin_id FROM stock_movement"
        )
    ).scalars().all()

    for insulin_id in insulin_ids:
        totals = bind.execute(
            sa.text(
                """
                SELECT
                    COALESCE(SUM(quantity_units), 0) AS current_stock,
                    COALESCE(
                        SUM(quantity_units) FILTER (
                            WHERE movement_type = 'STOCK_IN'
                        ),
                        0
                    ) AS stock_in_total,
                    MIN(occurred_at) AS earliest_occurred_at
                FROM stock_movement
                WHERE insulin_id = :insulin_id
                """
            ),
            {"insulin_id": insulin_id},
        ).one()

        current_stock = totals.current_stock
        stock_in_total = totals.stock_in_total
        earliest_occurred_at = totals.earliest_occurred_at

        initial_units = (
            stock_in_total
            if stock_in_total > 0
            else max(current_stock, 0)
        )
        container_status_value = (
            'EMPTY' if current_stock <= 0 else 'OPEN'
        )

        container_id = bind.execute(
            sa.text(
                """
                INSERT INTO insulin_container (
                    insulin_id, initial_units, status, opened_at, created_at
                ) VALUES (
                    :insulin_id, :initial_units, :status, :opened_at, :opened_at
                )
                RETURNING id
                """
            ),
            {
                "insulin_id": insulin_id,
                "initial_units": initial_units,
                "status": container_status_value,
                "opened_at": earliest_occurred_at,
            },
        ).scalar_one()

        bind.execute(
            sa.text(
                """
                UPDATE stock_movement
                SET container_id = :container_id
                WHERE insulin_id = :insulin_id
                """
            ),
            {"container_id": container_id, "insulin_id": insulin_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('stock_movement', 'container_id', nullable=True)
    op.drop_constraint(
        'stock_movement_group_id_fkey',
        'stock_movement',
        type_='foreignkey',
    )
    op.drop_constraint(
        'stock_movement_container_id_fkey',
        'stock_movement',
        type_='foreignkey',
    )
    op.drop_column('stock_movement', 'group_id')
    op.drop_column('stock_movement', 'container_id')
    op.drop_table('insulin_container')

    container_status = sa.Enum(name='container_status')
    container_status.drop(op.get_bind(), checkfirst=True)
