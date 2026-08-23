from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import MovementType, StockMovement, User
from app.schemas import (
    StockAdjustmentCreate,
    StockInCreate,
    StockInUpdate,
    StockMovementResponse,
    StockSummaryResponse,
)
from app.services.insulin_service import (
    ensure_insulin_active,
    get_owned_insulin,
)
from app.services.stock_service import calculate_current_stock


router = APIRouter(
    prefix="/api/insulins",
    tags=["stock"],
)


@router.post(
    "/{insulin_id}/stock",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_stock(
    insulin_id: int,
    stock_data: StockInCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)

    units_per_container = (
        insulin.concentration_units_per_ml
        * insulin.container_volume_ml
    )
    total_units = units_per_container * Decimal(stock_data.containers)

    movement = StockMovement(
        insulin_id=insulin.id,
        movement_type=MovementType.STOCK_IN,
        quantity_units=total_units,
        notes=f"Entrada de {stock_data.containers} recipiente(s)",
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.get(
    "/{insulin_id}/stock",
    response_model=StockSummaryResponse,
)
def get_stock(
    insulin_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)
    current_stock = calculate_current_stock(db, insulin.id)

    return {
        "insulin_id": insulin.id,
        "insulin_name": insulin.name,
        "current_stock_units": current_stock,
    }


@router.post(
    "/{insulin_id}/adjustments",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
)
def adjust_stock(
    insulin_id: int,
    adjustment_data: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)
    ensure_insulin_active(insulin)

    current_stock = calculate_current_stock(db, insulin.id)
    actual_stock = adjustment_data.actual_stock_units
    difference = actual_stock - current_stock

    if difference == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "O estoque informado já é igual "
                "ao estoque calculado pelo sistema."
            ),
        )

    movement = StockMovement(
        insulin_id=insulin.id,
        movement_type=MovementType.ADJUSTMENT,
        quantity_units=difference,
        occurred_at=datetime.now(timezone.utc),
        occurred_time_known=True,
        notes=adjustment_data.notes.strip(),
    )

    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.patch(
    "/{insulin_id}/stock/{movement_id}",
    response_model=StockMovementResponse,
)
def update_stock_entry(
    insulin_id: int,
    movement_id: int,
    stock_data: StockInUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insulin = get_owned_insulin(db, insulin_id, current_user)

    movement = db.scalar(
        select(StockMovement).where(
            StockMovement.id == movement_id,
            StockMovement.insulin_id == insulin.id,
            StockMovement.movement_type == MovementType.STOCK_IN,
        )
    )

    if movement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrada de estoque não encontrada.",
        )

    units_per_container = (
        insulin.concentration_units_per_ml
        * insulin.container_volume_ml
    )
    new_quantity = units_per_container * stock_data.containers
    current_stock = calculate_current_stock(db, insulin.id)
    projected_stock = current_stock - movement.quantity_units + new_quantity

    if projected_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Essa alteração deixaria o estoque atual negativo. "
                f"Estoque resultante: {projected_stock} U."
            ),
        )

    movement.quantity_units = new_quantity
    db.commit()
    db.refresh(movement)
    return movement
