from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import auth, skills, conversations, messages, models_router
from app.services.auth_service import AuthError
from app.services.skill_service import SkillError
from app.services.llm_service import LLMError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    await init_db()
    yield


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

# Routers
app.include_router(auth.router)
app.include_router(skills.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(models_router.router)


# Global exception handlers
@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(SkillError)
async def skill_error_handler(request: Request, exc: SkillError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/")
async def root():
    return {"service": "AI Agent Skills Workspace", "version": "1.0.0"}
