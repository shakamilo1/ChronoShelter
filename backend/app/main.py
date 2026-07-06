from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import anime, health

app = FastAPI(title="ChronoShelter")
app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")
app.mount("/media", StaticFiles(directory="media", check_dir=False), name="media")
app.include_router(health.router)
app.include_router(anime.router)
