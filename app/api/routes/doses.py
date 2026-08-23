from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import MovementType, StockMovement, User
from app.schemas import (
    DoseBatchCreate,
    DoseCreate,
    DoseUpdate,
    StockMovementResponse,
)
from app.services.dose_service import resolve_dose_datetime
from app.services.insulin_service import get_owned_insulin
from app.services.stock_service import calculate_current_stock


router = APIRouter(
    prefix="/api/insulins",
    tags=["doses"],
)


@router.post(
    "/{insulin_id}/doses",
    response_model=StockMovementResponse,
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

    movement = StockMovement(
        insulin_id=insulin.id,
        movement_type=MovementType.DOSE,
        quantity_units=-dose_data.units,
        occurred_at=occurred_at,
        occurred_time_known=time_known,
        notes=dose_data.notes,
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.patch(
    "/{insulin_id}/doses/{dose_id}",
    response_model=StockMovementResponse,
)
def update_dose(
    insulin_id: int,
    dose_id: int,
    dose_data: DoseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)

    movement = db.scalar(
        select(StockMovement).where(
            StockMovement.id == dose_id,
            StockMovement.insulin_id == insulin.id,
            StockMovement.movement_type == MovementType.DOSE,
        )
    )

    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicação não encontrada.",
        )

    current_stock = calculate_current_stock(db, insulin.id)
    old_units = abs(movement.quantity_units)
    available_units = current_stock + old_units

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

    movement.quantity_units = -dose_data.units
    movement.occurred_at = occurred_at
    movement.occurred_time_known = time_known
    movement.notes = dose_data.notes

    db.commit()
    db.refresh(movement)
    return movement
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

    movement = db.scalar(
        select(StockMovement).where(
            StockMovement.id == dose_id,
            StockMovement.insulin_id == insulin.id,
            StockMovement.movement_type == MovementType.DOSE,
        )
    )

    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aplicação não encontrada.",
        )

    db.delete(movement)
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

    movements: list[StockMovement] = []

    for item in batch_data.doses:
        occurred_at, time_known = resolve_dose_datetime(
            item.occurred_date,
            item.occurred_time,
        )
        movements.append(
            StockMovement(
                insulin_id=insulin.id,
                movement_type=MovementType.DOSE,
                quantity_units=-item.units,
                occurred_at=occurred_at,
                occurred_time_known=time_known,
                notes=item.notes,
            )
        )

    db.add_all(movements)
    db.commit()

    for movement in movements:
        db.refresh(movement)

    return movements
