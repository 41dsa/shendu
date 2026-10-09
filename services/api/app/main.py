import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.middleware.access_log import SafeAccessLogMiddleware
from app.routers import (
    admin,
    admin_research,
    admin_standards,
    ai_config,
    auth,
    coach,
    disputes,
    exam,
    grading,
    license,
    questions,
    submissions,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI申论教练 API", version="0.1.1", lifespan=lifespan)

logging.basicConfig(level=logging.INFO)

app.add_middleware(SafeAccessLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(license.router)
app.include_router(ai_config.router)
app.include_router(admin.router)
app.include_router(admin_research.router)
app.include_router(admin_standards.router)
app.include_router(disputes.router)
app.include_router(exam.router)
app.include_router(questions.router)
app.include_router(submissions.router)
app.include_router(grading.router)
app.include_router(coach.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.app_env}
