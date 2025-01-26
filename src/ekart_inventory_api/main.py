from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette_context.middleware import RawContextMiddleware
from starlette_context.plugins import CorrelationIdPlugin, RequestIdPlugin

# from .routers import 
from .settings.config import settings

description = """
Police Evidence Management System
"""

app = FastAPI(
    title="EKart",
    description=description,
    version="0.0.1",
    responses={404: {"description": "Not found"}},
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


origins = settings.get("ALLOWED_ORIGINS") or []

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PATCH", "PUT"],
    allow_headers=[
        "Access-Control-Allow-Headers",
        "Content-Type",
        "Authorization",
        "Access-Control-Allow-Origin",
        "Client",
    ],
)

app.add_middleware(
    RawContextMiddleware, plugins=[RequestIdPlugin(), CorrelationIdPlugin()]
)
# app.include_router(agency.agency_router)