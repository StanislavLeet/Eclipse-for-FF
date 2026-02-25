import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import auth, games, turns
from app.routers import research
from app.routers import ships
from app.routers import combat
from app.routers import council

app = FastAPI(
    title="Eclipse: Second Dawn for the Galaxy",
    description="Browser-based digital implementation of Eclipse Second Dawn",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(games.router)
app.include_router(turns.router)
app.include_router(research.router)
app.include_router(ships.router)
app.include_router(combat.router)
app.include_router(council.router)
app.include_router(council.council_meta_router)

# Serve frontend static files if the directory exists
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
