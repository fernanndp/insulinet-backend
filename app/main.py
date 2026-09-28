from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.routes import (
    auth,
    doses,
    health,
    insulins,
    stock,
    users,
)
from app.core.config import CORS_ORIGINS
from app.core.rate_limit import (
    limiter,
    rate_limit_exceeded_handler,
)


app = FastAPI(
    title="Insulinet API",
    version="0.1.0",
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    rate_limit_exceeded_handler,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(insulins.router)
app.include_router(stock.router)
app.include_router(doses.router)