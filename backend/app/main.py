from fastapi import FastAPI
from app.api.auth import router as auth_router

from app.api.orgs import router as orgs_router

app = FastAPI(title="SaaS Metering Platform", version="0.1.0")

# Simple health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

# Include API routers

# The auth router includes endpoints for user registration, login, and getting the current user.
app.include_router(auth_router)

# The orgs router includes endpoints for managing organizations and their members.
app.include_router(orgs_router)
