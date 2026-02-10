from fastapi import FastAPI
from app.api.auth import router as auth_router


app = FastAPI(title="SaaS Metering Platform", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(auth_router)