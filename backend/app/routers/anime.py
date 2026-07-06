from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates

from .. import repositories

templates = Jinja2Templates(directory="backend/app/templates")
router = APIRouter()

@router.get("/")
def index(request: Request, q: str | None = Query(default=None)):
    anime = repositories.list_anime(q=q)
    return templates.TemplateResponse("index.html", {"request": request, "anime": anime, "q": q or ""})

@router.get("/anime/{anime_id}")
def detail(request: Request, anime_id: int):
    anime = repositories.get_anime(anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    return templates.TemplateResponse("anime_detail.html", {"request": request, "anime": anime})
