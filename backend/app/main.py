from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.orgs import router as orgs_router
from app.api.api_keys import router as api_keys_router
from app.api.usage import router as usage_router
from app.core.quota import MonthlyQuotaExceededError

app = FastAPI(title="SaaS Metering Platform", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(MonthlyQuotaExceededError)
def monthly_quota_exceeded_handler(_, exc: MonthlyQuotaExceededError):
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Monthly quota exceeded",
            "limit": exc.limit,
            "used": exc.used,
            "resets_at": exc.resets_at,
        },
    )


# API Routers 
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(api_keys_router)
app.include_router(usage_router)
