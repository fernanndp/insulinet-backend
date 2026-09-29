from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

from sqlalchemy.orm import Session

from app.services.container_service import (
    calculate_container_remaining,
    get_container_stock_expiration,
    list_containers,
)


@dataclass
class StockExpirationSnapshot:
    expiration_date: date | None
    remaining_units: Decimal


def get_next_expiration_snapshot(
    db: Session,
    insulin_id: int,
) -> StockExpirationSnapshot:
    """
    Calcula o próximo vencimento usando o
    saldo REAL das canetas/frascos.

    Isso evita reconstruir o estoque a partir
    do histórico de movimentações e garante
    que o estoque considerado para validade
    nunca seja maior que o estoque disponível.
    """

    containers = list_containers(
        db,
        insulin_id,
    )

    expiration_buckets: dict[
        date,
        Decimal,
    ] = {}

    for container in containers:
        remaining_units = (
            calculate_container_remaining(
                db,
                container.id,
            )
        )

        if remaining_units <= 0:
            continue

        expiration_date = (
            get_container_stock_expiration(
                db,
                container.id,
            )
        )

        if expiration_date is None:
            continue

        expiration_buckets[
            expiration_date
        ] = (
            expiration_buckets.get(
                expiration_date,
                Decimal("0"),
            )
            + remaining_units
        )

    if not expiration_buckets:
        return StockExpirationSnapshot(
            expiration_date=None,
            remaining_units=Decimal("0"),
        )

    next_expiration_date = min(
        expiration_buckets.keys()
    )

    return StockExpirationSnapshot(
        expiration_date=(
            next_expiration_date
        ),
        remaining_units=(
            expiration_buckets[
                next_expiration_date
            ]
        ),
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
            "next_expiration_date":
                None,

            "days_until_expiration":
                None,

            "expiring_stock_units":
                None,

            "estimated_expiring_stock_end_date":
                None,

            "expiration_status":
                "NO_DATA",
        }

    days_until_expiration = (
        expiration_date
        - today
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
        average_daily_consumption
        is None
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
            days=int(
                days_to_consume
            )
        )
    )

    if (
        estimated_end_date
        > expiration_date
    ):
        expiration_status = (
            "AT_RISK"
        )

    elif (
        estimated_end_date
        == expiration_date
    ):
        expiration_status = (
            "SAME_DAY"
        )

    else:
        expiration_status = (
            "SAFE"
        )

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