import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from routers import auth, api

app = FastAPI(docs_url=None, redoc_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev-secret-change-in-production"),
    max_age=7 * 24 * 60 * 60,
    https_only=os.getenv("ENV") == "production",
    same_site="lax",
)

app.include_router(auth.router, prefix="/auth")
app.include_router(api.router,  prefix="/api")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Skip expected HTTP errors — only log true surprises
    if isinstance(exc, HTTPException):
        raise exc
    from services.logger import log_error
    log_error(
        f"Unhandled exception: {exc}",
        exc=exc,
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("static/index.html")
