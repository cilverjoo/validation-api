import os

import sentry_sdk

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.server_config import allowed_origins
from app.routers import sensor_fusion, validation


sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=1.0,
)

app = FastAPI(openapi_url=f"/openapi.json", docs_url=f"/docs")


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600
)

app.include_router(sensor_fusion.router)
app.include_router(validation.router)


@app.get("/healthz", description="api readiness check")
def readiness_check():
    return JSONResponse(status_code=200, content={"message": "dp-api is ready"})


@app.on_event("startup")
async def startup_event():
    print("Fast API is starting up")


@app.on_event("shutdown")
async def shutdown_event():
    print("Fast API is shutting down")
