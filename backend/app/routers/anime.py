from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .. import repositories

templates = Jinja2Templates(directory="backend/app/templates")
router = APIRouter()

@router.get("/")
def index(request: Request, q: str | None = Query(default=None)):
    anime = repositories.list_anime(q=q)
    return templates.TemplateResponse("index.html", {"request": request, "anime": anime, "q": q or ""})

@router.post("/anime/{anime_id}/collect")
def collect(anime_id: int):
    repositories.one_click_collect(anime_id)
    return RedirectResponse(url="/", status_code=303)

@router.get("/anime/{anime_id}")
def detail(request: Request, anime_id: int):
    anime = repositories.get_anime(anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    return templates.TemplateResponse("anime_detail.html", {"request": request, "anime": anime})

@router.get("/anime/{anime_id}/collection/edit")
def edit_collection(request: Request, anime_id: int):
    anime = repositories.get_anime(anime_id)
    if not anime:
        raise HTTPException(status_code=404, detail="Anime not found")
    return templates.TemplateResponse("collection_edit.html", {"request": request, "anime": anime})

@router.post("/anime/{anime_id}/collection/edit")
def save_collection(
    anime_id: int,
    collected: str | None = Form(default=None),
    media_type: str = Form(default=""),
    subtitle_group: str = Form(default=""),
    source_site: str = Form(default=""),
    collection_date: str = Form(default=""),
    my_rating: str = Form(default=""),
    notes: str = Form(default=""),
    extra: str = Form(default=""),
):
    repositories.save_collection(
        anime_id,
        {
            "collected": collected,
            "media_type": media_type,
            "subtitle_group": subtitle_group,
            "source_site": source_site,
            "collection_date": collection_date,
            "my_rating": my_rating,
            "notes": notes,
            "extra": extra,
        },
    )
    return RedirectResponse(url=f"/anime/{anime_id}", status_code=303)
