from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.core.password_policy import (
    validate_password_strength,
)
from app.core.rate_limit import limiter
from app.core.security import (
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    UserResponse,
)


router = APIRouter(
    prefix="/api/users",
    tags=["users"],
)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user


@router.patch(
    "/me/password",
    response_model=ChangePasswordResponse,
)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    if not verify_password(
        data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )

    if verify_password(
        data.new_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A nova senha deve ser "
                "diferente da senha atual."
            ),
        )

    try:
        validate_password_strength(
            data.new_password,
            name=current_user.name,
            email=current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    current_user.password_hash = hash_password(
        data.new_password
    )

    db.commit()

    return {
        "message": "Senha alterada com sucesso."
    }