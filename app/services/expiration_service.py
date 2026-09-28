from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MovementType, StockMovement


@dataclass
class StockExpirationSnapshot:
    expiration_date: date | None
    remaining_units: Decimal


def get_next_expiration_snapshot(
    db: Session,
    insulin_id: int,
) -> StockExpirationSnapshot:
    statement = (
        select(StockMovement)
        .where(
            StockMovement.insulin_id == insulin_id
        )
        .order_by(
            StockMovement.occurred_at,
            StockMovement.id,
        )
    )

    movements = db.scalars(
        statement
    ).all()

    buckets: list[dict] = []

    for movement in movements:
        quantity = Decimal(
            movement.quantity_units
        )

        if quantity > 0:
            buckets.append(
                {
                    "remaining_units": quantity,
                    "expiration_date": (
                        movement.expiration_date
                        if movement.movement_type
                        == MovementType.STOCK_IN
                        else None
                    ),
                }
            )

            continue

        if quantity >= 0:
            continue

        units_to_consume = abs(quantity)

        for bucket in buckets:
            if units_to_consume <= 0:
                break

            available = Decimal(
                bucket["remaining_units"]
            )

            if available <= 0:
                continue

            consumed = min(
                available,
                units_to_consume,
            )

            bucket["remaining_units"] = (
                available - consumed
            )

            units_to_consume -= consumed

    tracked_buckets = [
        bucket
        for bucket in buckets
        if (
            Decimal(
                bucket["remaining_units"]
            ) > 0
            and bucket["expiration_date"]
            is not None
        )
    ]

    if not tracked_buckets:
        return StockExpirationSnapshot(
            expiration_date=None,
            remaining_units=Decimal("0"),
        )

    next_expiration_date = min(
        bucket["expiration_date"]
        for bucket in tracked_buckets
    )

    remaining_units = sum(
        (
            Decimal(
                bucket["remaining_units"]
            )
            for bucket in tracked_buckets
            if bucket["expiration_date"]
            == next_expiration_date
        ),
        Decimal("0"),
    )

    return StockExpirationSnapshot(
        expiration_date=next_expiration_date,
        remaining_units=remaining_units,
    )


def build_expiration_projection(
    snapshot: StockExpirationSnapshot,
    average_daily_consumption: Decimal | None,
    today: date,
) -> dict:
    expiration_date = (
        snapshot.expiration_date
    )

    if expiration_date is None:
        return {
            "next_expiration_date": None,
            "days_until_expiration": None,
            "expiring_stock_units": None,
            "estimated_expiring_stock_end_date": None,
            "expiration_status": "NO_DATA",
        }

    days_until_expiration = (
        expiration_date - today
    ).days

    if days_until_expiration < 0:
        return {
            "next_expiration_date":
                expiration_date,
            "days_until_expiration":
                days_until_expiration,
            "expiring_stock_units":
                snapshot.remaining_units,
            "estimated_expiring_stock_end_date":
                None,
            "expiration_status":
                "EXPIRED",
        }

    if (
        average_daily_consumption is None
        or average_daily_consumption <= 0
    ):
        return {
            "next_expiration_date":
                expiration_date,
            "days_until_expiration":
                days_until_expiration,
            "expiring_stock_units":
                snapshot.remaining_units,
            "estimated_expiring_stock_end_date":
                None,
            "expiration_status":
                "NO_PROJECTION",
        }

    days_to_consume = (
        snapshot.remaining_units
        / average_daily_consumption
    ).to_integral_value(
        rounding=ROUND_CEILING
    )

    estimated_end_date = (
        today
        + timedelta(
            days=int(days_to_consume)
        )
    )

    if estimated_end_date > expiration_date:
        expiration_status = "AT_RISK"

    elif estimated_end_date == expiration_date:
        expiration_status = "SAME_DAY"

    else:
        expiration_status = "SAFE"

    return {
        "next_expiration_date":
            expiration_date,
        "days_until_expiration":
            days_until_expiration,
        "expiring_stock_units":
            snapshot.remaining_units,
        "estimated_expiring_stock_end_date":
            estimated_end_date,
        "expiration_status":
            expiration_status,
    }