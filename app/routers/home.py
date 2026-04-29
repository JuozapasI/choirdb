# app/routers/home.py
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import database, models, auth

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    q: Optional[str] = None,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Home page: display approved scores and user's pending submissions.
    Optional search query `q` to filter scores by multiple fields.
    """
    query = db.query(models.Score)

    if q:
        like_pattern = f"%{q}%"
        query = query.filter(
            or_(
                models.Score.title.ilike(like_pattern),
                models.Score.composer.ilike(like_pattern),
                models.Score.lyrics_author.ilike(like_pattern),
                models.Score.language.ilike(like_pattern),
                models.Score.source.ilike(like_pattern),
                models.Score.liturgical_time.ilike(like_pattern),
                models.Score.mass_part.ilike(like_pattern),
                models.Score.tags.ilike(like_pattern),
                models.Score.parent_issue.ilike(like_pattern),
                models.Score.additional_info.ilike(like_pattern),
                models.Score.archive_id.ilike(like_pattern),
            )
        )

    scores = (
        query
        .filter(
            (models.Score.status == models.ScoreStatus.APPROVED) |
            ((models.Score.status == models.ScoreStatus.PENDING) & 
             (models.Score.submitted_by_id == current_user.id))
        )
        .order_by(
            models.Score.status.desc(),  # pending first
            models.Score.title.asc()
        )
        .all()
    )

    return templates.TemplateResponse(
        "home.html",
        {"request": request, "scores": scores, "user": current_user}
    )

'''
@router.get("/test-base", response_class=HTMLResponse)
def test_base(request: Request):
    """Simple test page for base template rendering."""
    test_user = {"username": "TestUser", "role": {"value": "user"}}
    return templates.TemplateResponse("test_base.html", {"request": request, "user": test_user})
'''
