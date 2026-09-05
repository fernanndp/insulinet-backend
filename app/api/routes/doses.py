from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import InsulinContainer, MovementType, StockMovement, User
from app.schemas import (
    DoseBatchCreate,
    DoseCreate,
    DoseUpdate,
    StockMovementResponse,
)
from app.services.container_service import sync_container_status
from app.services.dose_service import resolve_dose_datetime
from app.services.insulin_service import get_owned_insulin
from app.services.stock_service import (
    InsufficientStockError,
    calculate_current_stock,
    distribute_negative_delta,
)


router = APIRouter(
    prefix="/api/insulins",
    tags=["doses"],
)


def _get_dose_group(
    db: Session,
    insulin_id: int,
    dose_id: int,
) -> list[StockMovement]:
    anchor = db.scalar(
        select(StockMovement).where(
            StockMovement.id == dose_id,
            StockMovement.insulin_id == insulin_id,
            StockMovement.movement_type == MovementType.DOSE,
        )
    )

    if anchor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicação não encontrada.",
        )

    group_key = anchor.group_id or anchor.id

    return list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.insulin_id == insulin_id,
                StockMovement.movement_type == MovementType.DOSE,
                or_(
                    StockMovement.id == group_key,
                    StockMovement.group_id == group_key,
                ),
            )
        ).all()
    )


def _delete_dose_group(
    db: Session,
    group_movements: list[StockMovement],
) -> dict[int, InsulinContainer]:
    affected_containers = {
        movement.container_id: movement.container
        for movement in group_movements
    }

    # group_id is a self-referencing FK on this table, and a single
    # flush() batches same-table deletes together regardless of the
    # order db.delete() was called in — so children (group_id set)
    # are removed in their own flush before the anchor row they
    # point to is removed in a second one.
    children = [
        movement
        for movement in group_movements
        if movement.group_id is not None
    ]
    anchors = [
        movement
        for movement in group_movements
        if movement.group_id is None
    ]

    for movement in children:
        db.delete(movement)
    db.flush()

    for movement in anchors:
        db.delete(movement)
    db.flush()

    return affected_containers


@router.post(
    "/{insulin_id}/doses",
    response_model=list[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
def register_dose(
    insulin_id: int,
    dose_data: DoseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    current_stock = calculate_current_stock(db, insulin.id)

    if dose_data.units > current_stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Estoque insuficiente. "
                f"Estoque atual: {current_stock} U"
            ),
        )

    occurred_at, time_known = resolve_dose_datetime(
        dose_data.occurred_date,
        dose_data.occurred_time,
    )

    try:
        movements = distribute_negative_delta(
            db,
            insulin,
            dose_data.units,
            MovementType.DOSE,
            occurred_at,
            time_known,
            dose_data.notes,
        )
    except InsufficientStockError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Estoque insuficiente entre as canetas/frascos disponíveis.",
        )

    db.commit()

    for movement in movements:
        db.refresh(movement)

    return movements


@router.patch(
    "/{insulin_id}/doses/{dose_id}",
    response_model=list[StockMovementResponse],
)
def update_dose(
    insulin_id: int,
    dose_id: int,
    dose_data: DoseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)

    group_movements = _get_dose_group(db, insulin.id, dose_id)

    old_units_total = sum(
        (abs(movement.quantity_units) for movement in group_movements),
        Decimal("0"),
    )

    current_stock = calculate_current_stock(db, insulin.id)
    available_units = current_stock + old_units_total

    if dose_data.units > available_units:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Estoque insuficiente para essa alteração. "
                f"Máximo disponível: {available_units} U"
            ),
        )

    occurred_at, time_known = resolve_dose_datetime(
        dose_data.occurred_date,
        dose_data.occurred_time,
    )

    affected_containers = _delete_dose_group(db, group_movements)

    for container in affected_containers.values():
        sync_container_status(db, container)

    try:
        new_movements = distribute_negative_delta(
            db,
            insulin,
            dose_data.units,
            MovementType.DOSE,
            occurred_at,
            time_known,
            dose_data.notes,
        )
    except InsufficientStockError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Estoque insuficiente entre as canetas/frascos disponíveis.",
        )

    db.commit()

    for movement in new_movements:
        db.refresh(movement)

    return new_movements


@router.delete(
    "/{insulin_id}/doses/{dose_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_dose(
    insulin_id: int,
    dose_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(
        db,
        insulin_id,
        current_user,
    )

    group_movements = _get_dose_group(db, insulin.id, dose_id)

    affected_containers = _delete_dose_group(db, group_movements)

    for container in affected_containers.values():
        sync_container_status(db, container)

    db.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.post(
    "/{insulin_id}/dose-batches",
    response_model=list[StockMovementResponse],
    status_code=status.HTTP_201_CREATED,
)
def register_dose_batch(
    insulin_id: int,
    batch_data: DoseBatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    current_stock = calculate_current_stock(db, insulin.id)

    total_units = sum(
        (item.units for item in batch_data.doses),
        Decimal("0"),
    )

    if total_units > current_stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Estoque insuficiente para registrar todas as aplicações. "
                f"Estoque atual: {current_stock} U. "
                f"Total informado: {total_units} U."
            ),
        )

    all_movements: list[StockMovement] = []

    for item in batch_data.doses:
        occurred_at, time_known = resolve_dose_datetime(
            item.occurred_date,
            item.occurred_time,
        )

        try:
            movements = distribute_negative_delta(
                db,
                insulin,
                item.units,
                MovementType.DOSE,
                occurred_at,
                time_known,
                item.notes,
            )
        except InsufficientStockError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Estoque insuficiente para registrar todas as aplicações."
                ),
            )

        all_movements.extend(movements)

    db.commit()

    for movement in all_movements:
        db.refresh(movement)

    return all_movements
