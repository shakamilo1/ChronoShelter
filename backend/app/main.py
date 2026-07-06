from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import anime, health

app = FastAPI(title="ChronoShelter")
app.mount("/static", StaticFiles(directory="backend/app/static"), name="static")
app.include_router(health.router)
app.include_router(anime.router)
