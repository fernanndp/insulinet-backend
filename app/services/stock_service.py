from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import StockMovement


def calculate_current_stock(
    db: Session,
    insulin_id: int,
) -> Decimal:
    statement = select(
        func.coalesce(
            func.sum(StockMovement.quantity_units),
            0,
        )
    ).where(
        StockMovement.insulin_id == insulin_id
    )

    result = db.scalar(statement)
    return Decimal(result)
