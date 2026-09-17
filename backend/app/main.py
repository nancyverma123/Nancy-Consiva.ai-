import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, chat, history, voice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("consiva")

settings = get_settings()

_INSECURE_SECRETS = {"insecure-dev-secret-change-me", "replace-with-a-long-random-secret", ""}
if settings.environment.lower() not in {"development", "dev", "local"} and (
    settings.jwt_secret_key in _INSECURE_SECRETS or len(settings.jwt_secret_key) < 32
):
    raise RuntimeError("JWT_SECRET_KEY must be set to a long random value outside development.")

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="Multilingual RAG chatbot API for Consiva - answers grounded in the approved knowledge base only.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Something went wrong. Please try again shortly."},
    )


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(history.router)
app.include_router(voice.router)


@app.get("/api/health", tags=["health"])
def health_check():
    return {"status": "ok", "app": settings.app_name}
