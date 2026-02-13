from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.orgs import router as orgs_router
from app.api.api_keys import router as api_keys_router

app = FastAPI(title="SaaS Metering Platform", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


# API Routers 
app.include_router(auth_router)
app.include_router(orgs_router)
app.include_router(api_keys_router)
