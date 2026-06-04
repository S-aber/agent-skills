import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, skills, conversations, messages, models_router, uploads, mcp
from app.services.auth_service import AuthError
from app.services.skill_service import SkillError
from app.services.llm_service import LLMError
from app.utils.logging import setup_logging, get_logger

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Application starting up...")
    await init_db()
    logger.info("Database tables initialized")
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title="AI Agent Skills Workspace",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    logger.info(
        "%s %s → %s (%.0fms)",
        request.method,
        request.url.path + (f"?{request.url.query}" if request.url.query else ""),
        response.status_code,
        duration_ms,
    )
    return response


# Routers
app.include_router(auth.router)
app.include_router(skills.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(models_router.router)
app.include_router(uploads.router)
app.include_router(mcp.router)


# Global exception handlers
@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    logger.warning("Auth error on %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(SkillError)
async def skill_error_handler(request: Request, exc: SkillError):
    logger.warning("Skill error on %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    logger.error("LLM error on %s: [%s] %s", request.url.path, exc.code, exc.message)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}},
    )


@app.get("/")
async def root():
    return {"service": "AI Agent Skills Workspace", "version": "1.0.0"}
