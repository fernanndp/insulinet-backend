from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine


router = APIRouter(tags=["health"])


@router.get("/")
def root():
    return {
        "status": "ok",
        "message": "Insulinet API funcionando",
    }


@router.get("/db-test")
def database_test():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        value = result.scalar()

    return {
        "database": "connected",
        "result": value,
    }
