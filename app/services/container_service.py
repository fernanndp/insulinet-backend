from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import APP_TIMEZONE
from app.models import (
    ContainerStatus,
    InsulinContainer,
    MovementType,
    StockMovement,
)


OPEN_EXPIRATION_WARNING_DAYS = 5


def list_containers(
    db: Session,
    insulin_id: int,
) -> list[InsulinContainer]:
    statement = (
        select(InsulinContainer)
        .where(
            InsulinContainer.insulin_id
            == insulin_id
        )
        .order_by(
            InsulinContainer.created_at,
            InsulinContainer.id,
        )
    )

    return list(
        db.scalars(
            statement
        ).all()
    )


def calculate_container_remaining(
    db: Session,
    container_id: int,
) -> Decimal:
    statement = (
        select(StockMovement)
        .where(
            StockMovement.container_id
            == container_id
        )
    )

    movements = (
        db.scalars(
            statement
        ).all()
    )

    return sum(
        (
            movement.quantity_units
            for movement in movements
        ),
        Decimal("0"),
    )


def get_container_stock_expiration(
    db: Session,
    container_id: int,
) -> date | None:
    statement = (
        select(StockMovement)
        .where(
            StockMovement.container_id
            == container_id,
            StockMovement.movement_type
            == MovementType.STOCK_IN,
        )
        .order_by(
            StockMovement.id
        )
    )

    movement = (
        db.scalars(
            statement
        ).first()
    )

    if movement is None:
        return None

    return movement.expiration_date


def sync_container_status(
    db: Session,
    container: InsulinContainer,
) -> None:
    if (
        container.status
        == ContainerStatus.DISCARDED
    ):
        return

    remaining = (
        calculate_container_remaining(
            db,
            container.id,
        )
    )

    if remaining <= 0:
        container.status = (
            ContainerStatus.EMPTY
        )
        return

    if (
        remaining
        == container.initial_units
    ):
        container.status = (
            ContainerStatus.SEALED
        )

        container.opened_at = None

        return

    container.status = (
        ContainerStatus.OPEN
    )

    db.flush()


def open_container(
    db: Session,
    container: InsulinContainer,
) -> None:
    if (
        container.status
        == ContainerStatus.SEALED
    ):
        container.status = (
            ContainerStatus.OPEN
        )

        container.opened_at = (
            datetime.now(
                timezone.utc
            )
        )

        db.flush()


def compute_container_expiration(
    container: InsulinContainer,
    open_validity_days: int,
    today_local: date,
    stock_expiration_date: date | None = None,
) -> dict:
    """
    Calcula o limite efetivo de uso.

    Para uma caneta aberta existem
    potencialmente dois limites:

    1. vencimento impresso da embalagem;
    2. prazo após a abertura.

    O limite efetivo é a data
    que ocorrer primeiro.
    """

    open_discard_date: date | None = None

    if (
        container.status
        == ContainerStatus.OPEN
        and container.opened_at
        is not None
    ):
        opened_at = (
            container.opened_at
        )

        if (
            opened_at.tzinfo
            is None
        ):
            opened_at = (
                opened_at.replace(
                    tzinfo=timezone.utc
                )
            )

        opened_local_date = (
            opened_at
            .astimezone(
                APP_TIMEZONE
            )
            .date()
        )

        open_discard_date = (
            opened_local_date
            + timedelta(
                days=open_validity_days
            )
        )

    candidates: list[
        tuple[str, date]
    ] = []

    if (
        stock_expiration_date
        is not None
    ):
        candidates.append(
            (
                "stock",
                stock_expiration_date,
            )
        )

    if (
        open_discard_date
        is not None
    ):
        candidates.append(
            (
                "opened",
                open_discard_date,
            )
        )

    if (
        container.status
        in (
            ContainerStatus.EMPTY,
            ContainerStatus.DISCARDED,
        )
    ):
        return {
            "expires_at":
                None,

            "days_until_expiration":
                None,

            "expiration_status":
                "not_applicable",

            "expiration_source":
                None,

            "stock_expiration_date":
                stock_expiration_date,

            "open_discard_date":
                open_discard_date,
        }

    if not candidates:
        return {
            "expires_at":
                None,

            "days_until_expiration":
                None,

            "expiration_status":
                "not_applicable",

            "expiration_source":
                None,

            "stock_expiration_date":
                stock_expiration_date,

            "open_discard_date":
                open_discard_date,
        }

    (
        expiration_source,
        effective_date,
    ) = min(
        candidates,
        key=lambda item: item[1],
    )

    days_until_expiration = (
        effective_date
        - today_local
    ).days

    if (
        days_until_expiration
        < 0
    ):
        expiration_status = (
            "expired"
        )

    elif (
        days_until_expiration
        <= OPEN_EXPIRATION_WARNING_DAYS
    ):
        expiration_status = (
            "expiring_soon"
        )

    else:
        expiration_status = (
            "ok"
        )

    expires_at = (
        datetime.combine(
            effective_date,
            time.min,
            tzinfo=APP_TIMEZONE,
        )
    )

    return {
        "expires_at":
            expires_at,

        "days_until_expiration":
            days_until_expiration,

        "expiration_status":
            expiration_status,

        "expiration_source":
            expiration_source,

        "stock_expiration_date":
            stock_expiration_date,

        "open_discard_date":
            open_discard_date,
    }


def get_available_containers_fifo(
    db: Session,
    insulin_id: int,
) -> list[InsulinContainer]:
    containers = (
        list_containers(
            db,
            insulin_id,
        )
    )

    open_containers = [
        container
        for container
        in containers
        if (
            container.status
            == ContainerStatus.OPEN
        )
    ]

    sealed_containers = [
        container
        for container
        in containers
        if (
            container.status
            == ContainerStatus.SEALED
        )
    ]

    return (
        open_containers
        + sealed_containers
    )